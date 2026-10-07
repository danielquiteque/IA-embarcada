"""Treina o modelo Hello World (seno), quantiza para int8 e gera main/model.cc.

Mesmo fluxo do notebook tflite_hello_world_training.ipynb da disciplina
(adaptado de tflite-micro/examples/hello_world/train.py), rodando localmente:

    python train/train_hello_world.py

Saídas em train/output/: SavedModel, hello_world_float.tflite, hello_world_int8.tflite
e o model.cc, que também é copiado para main/model.cc.
"""
import math
import os
import shutil

import numpy as np
import tensorflow as tf

SEED = 42
EPOCHS = 300
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output")
SAVED_MODEL_DIR = os.path.join(OUT_DIR, "saved_model")
MAIN_MODEL_CC = os.path.join(HERE, "..", "main", "model.cc")


def get_data(n=1000):
    # Valores uniformes em [0, 2π], cobrindo um ciclo completo do seno
    x = np.random.uniform(low=0, high=2 * math.pi, size=n).astype(np.float32)
    np.random.shuffle(x)
    return x, np.sin(x).astype(np.float32)


def create_model():
    model = tf.keras.Sequential([
        tf.keras.Input(shape=(1,)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(1),
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def convert_float(model):
    return tf.lite.TFLiteConverter.from_keras_model(model).convert()


def convert_int8(saved_model_dir, x_repr):
    def representative_dataset():
        for v in x_repr[:500]:
            yield [v.reshape(1, 1)]

    converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_dir)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    converter.representative_dataset = representative_dataset
    return converter.convert()


def predict_tflite(model_bytes, x):
    interp = tf.lite.Interpreter(model_content=model_bytes)
    interp.allocate_tensors()
    inp = interp.get_input_details()[0]
    out = interp.get_output_details()[0]
    preds = []
    for v in x:
        data = np.array([[v]], dtype=np.float32)
        if inp["dtype"] == np.int8:
            scale, zp = inp["quantization"]
            data = np.round(data / scale + zp).astype(np.int8)
        interp.set_tensor(inp["index"], data)
        interp.invoke()
        y = interp.get_tensor(out["index"]).astype(np.float32)
        if out["dtype"] == np.int8:
            scale, zp = out["quantization"]
            y = (y - zp) * scale
        preds.append(y[0][0])
    return np.array(preds)


def to_c_array(model_bytes):
    """Equivalente ao `xxd -i model.tflite > model.cc`, no formato esperado por model.h."""
    lines = []
    for i in range(0, len(model_bytes), 12):
        chunk = model_bytes[i:i + 12]
        lines.append("    " + ", ".join(f"0x{b:02x}" for b in chunk) + ",")
    lines[-1] = lines[-1].rstrip(",")
    return (
        "// Gerado por train/train_hello_world.py a partir de hello_world_int8.tflite\n"
        "// (equivalente a: xxd -i hello_world_int8.tflite > model.cc)\n\n"
        '#include "model.h"\n\n'
        "// Alinhado em 8 bytes para garantir acessos de 64 bits alinhados.\n"
        "alignas(8) const unsigned char g_model[] = {\n"
        + "\n".join(lines)
        + "};\n"
        f"const int g_model_len = {len(model_bytes)};\n"
    )


def main():
    np.random.seed(SEED)
    tf.random.set_seed(SEED)
    os.makedirs(OUT_DIR, exist_ok=True)

    x, y = get_data()
    model = create_model()
    model.fit(x, y, epochs=EPOCHS, validation_split=0.2, batch_size=64, verbose=0)
    model.export(SAVED_MODEL_DIR)

    float_bytes = convert_float(model)
    int8_bytes = convert_int8(SAVED_MODEL_DIR, x)
    for name, data in (("hello_world_float.tflite", float_bytes), ("hello_world_int8.tflite", int8_bytes)):
        with open(os.path.join(OUT_DIR, name), "wb") as f:
            f.write(data)

    # Avaliação em pontos novos e igualmente espaçados
    x_test = np.linspace(0, 2 * math.pi, 200, dtype=np.float32)
    y_test = np.sin(x_test)
    print(f"{'Modelo':<10} {'Tamanho':>10} {'MAE':>8} {'RMSE':>8}")
    for name, data in (("float32", float_bytes), ("int8", int8_bytes)):
        err = predict_tflite(data, x_test) - y_test
        print(f"{name:<10} {len(data):>8} B {np.mean(np.abs(err)):>8.4f} {np.sqrt(np.mean(err ** 2)):>8.4f}")

    model_cc = os.path.join(OUT_DIR, "model.cc")
    with open(model_cc, "w", encoding="utf-8") as f:
        f.write(to_c_array(int8_bytes))
    shutil.copyfile(model_cc, MAIN_MODEL_CC)
    print(f"model.cc gerado ({len(int8_bytes)} bytes) e copiado para main/model.cc")


if __name__ == "__main__":
    main()
