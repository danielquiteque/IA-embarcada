"""Gera o dataset, treina, quantiza (int8) e exporta o classificador de orientação do MPU6050.

    python train/train_orientacao.py

Entradas (6): ax, ay, az em g e gx, gy, gz em °/s divididos por 250 (fundo de escala).
Classes (7): orientação estática pelo eixo que aponta para cima (Z+, Z-, X+, X-, Y+, Y-) ou "em rotação".

Sem uma placa física para coletar dados, o dataset é sintético e segue a física do sensor:
parado, o acelerômetro mede só a gravidade (vetor de ~1 g apontando para cima no referencial da
placa); girando, o giroscópio mede a velocidade angular e o acelerômetro sofre ruído extra.

Saídas: train/dataset_orientacao.csv, train/output/*.tflite e main/model.cc.
"""
import os
import shutil

import numpy as np
import tensorflow as tf

SEED = 42
N_STATIC = 7000
N_ROTATING = 1500
GYRO_SCALE = 250.0  # ±250 °/s, igual ao main.cc
ACCEL_RANGE = 2.0   # ±2 g
EPOCHS = 80
LABELS = [
    "plana, face para cima", "plana, face para baixo",
    "em pe, eixo X para cima", "em pe, eixo X para baixo",
    "de lado, eixo Y para cima", "de lado, eixo Y para baixo",
    "em rotacao",
]
ROTATING = 6

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output")
SAVED_MODEL_DIR = os.path.join(OUT_DIR, "saved_model")
DATASET_CSV = os.path.join(HERE, "dataset_orientacao.csv")
MAIN_MODEL_CC = os.path.join(HERE, "..", "main", "model.cc")


def random_directions(rng, n):
    v = rng.normal(size=(n, 3))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def up_axis_label(directions):
    """Classe do eixo que aponta para cima: 0=Z+, 1=Z-, 2=X+, 3=X-, 4=Y+, 5=Y-."""
    axis = np.argmax(np.abs(directions), axis=1)          # 0=x, 1=y, 2=z
    negative = directions[np.arange(len(directions)), axis] < 0
    base = np.array([2, 4, 0])[axis]                        # x->2, y->4, z->0
    return base + negative.astype(int)


def make_dataset(rng):
    # Parado: gravidade em direção qualquer, magnitude variada (inclui valores "irreais" que o
    # painel do Wokwi permite), ruído pequeno e giroscópio com no máximo 30 °/s de tremor.
    d = random_directions(rng, N_STATIC)
    accel = d * rng.uniform(0.7, 1.5, (N_STATIC, 1)) + rng.normal(0, 0.03, (N_STATIC, 3))
    gyro = random_directions(rng, N_STATIC) * rng.uniform(0, 30, (N_STATIC, 1))
    x_static = np.hstack([accel, gyro])
    y_static = up_axis_label(d)

    # Em rotação: qualquer orientação, 60 a 250 °/s em eixo aleatório e mais ruído de aceleração.
    d = random_directions(rng, N_ROTATING)
    accel = d * rng.uniform(0.7, 1.5, (N_ROTATING, 1)) + rng.normal(0, 0.15, (N_ROTATING, 3))
    gyro = random_directions(rng, N_ROTATING) * rng.uniform(60, 250, (N_ROTATING, 1))
    x_rot = np.hstack([accel, gyro])
    y_rot = np.full(N_ROTATING, ROTATING)

    x = np.vstack([x_static, x_rot]).astype(np.float32)
    y = np.concatenate([y_static, y_rot])
    # Saturação do sensor, como no hardware
    x[:, :3] = np.clip(x[:, :3], -ACCEL_RANGE, ACCEL_RANGE)
    x[:, 3:] = np.clip(x[:, 3:], -GYRO_SCALE, GYRO_SCALE)
    order = rng.permutation(len(y))
    return x[order], y[order]


def to_features(raw):
    f = raw.copy()
    f[:, 3:] /= GYRO_SCALE
    return f


def create_model():
    model = tf.keras.Sequential([
        tf.keras.Input(shape=(6,)),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(len(LABELS), activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


def convert_int8(saved_model_dir, x_repr):
    def representative_dataset():
        for v in x_repr[:1000]:
            yield [v.reshape(1, -1)]

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
    inp, out = interp.get_input_details()[0], interp.get_output_details()[0]
    preds = []
    for v in x:
        data = v.reshape(1, -1).astype(np.float32)
        if inp["dtype"] == np.int8:
            scale, zp = inp["quantization"]
            data = np.clip(np.round(data / scale + zp), -128, 127).astype(np.int8)
        interp.set_tensor(inp["index"], data)
        interp.invoke()
        preds.append(int(np.argmax(interp.get_tensor(out["index"])[0])))
    return np.array(preds)


def to_c_array(model_bytes):
    lines = ["    " + ", ".join(f"0x{b:02x}" for b in model_bytes[i:i + 12]) + ","
             for i in range(0, len(model_bytes), 12)]
    lines[-1] = lines[-1].rstrip(",")
    return (
        "// Gerado por train/train_orientacao.py a partir de orientacao_int8.tflite\n"
        "// (equivalente a: xxd -i orientacao_int8.tflite > model.cc)\n\n"
        '#include "model.h"\n\n'
        "alignas(8) const unsigned char g_model[] = {\n" + "\n".join(lines) + "};\n"
        f"const int g_model_len = {len(model_bytes)};\n"
    )


def main():
    rng = np.random.default_rng(SEED)
    tf.random.set_seed(SEED)
    os.makedirs(OUT_DIR, exist_ok=True)

    raw, y = make_dataset(rng)
    header = "ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,classe"
    np.savetxt(DATASET_CSV, np.hstack([raw, y[:, None]]), delimiter=",", header=header,
               comments="", fmt=["%.4f"] * 6 + ["%d"])
    print(f"Dataset: {len(y)} amostras -> {os.path.relpath(DATASET_CSV, HERE)}")
    for c, name in enumerate(LABELS):
        print(f"  {c} {name:<28} {np.sum(y == c):>5}")

    x = to_features(raw)
    n_test = len(y) // 5
    x_test, y_test, x_train, y_train = x[:n_test], y[:n_test], x[n_test:], y[n_test:]

    model = create_model()
    model.fit(x_train, y_train, epochs=EPOCHS, batch_size=64, validation_split=0.15, verbose=0)
    model.export(SAVED_MODEL_DIR)

    float_bytes = tf.lite.TFLiteConverter.from_keras_model(model).convert()
    int8_bytes = convert_int8(SAVED_MODEL_DIR, x_train)
    for name, data in (("orientacao_float.tflite", float_bytes), ("orientacao_int8.tflite", int8_bytes)):
        with open(os.path.join(OUT_DIR, name), "wb") as f:
            f.write(data)

    print(f"\n{'Modelo':<10} {'Tamanho':>10} {'Acurácia (teste)':>18}")
    preds = {}
    for name, data in (("float32", float_bytes), ("int8", int8_bytes)):
        preds[name] = predict_tflite(data, x_test)
        print(f"{name:<10} {len(data):>8} B {np.mean(preds[name] == y_test):>17.2%}")

    print("\nMatriz de confusão do int8 (linhas = real, colunas = previsto):")
    cm = np.zeros((len(LABELS), len(LABELS)), dtype=int)
    for t, p in zip(y_test, preds["int8"]):
        cm[t, p] += 1
    print("      " + " ".join(f"{c:>5}" for c in range(len(LABELS))))
    for c in range(len(LABELS)):
        print(f"  {c:>2}  " + " ".join(f"{v:>5}" for v in cm[c]))

    # Casos que podem ser reproduzidos no painel do MPU6050 no Wokwi
    cases = [
        (0, 0, 1, 0, 0, 0), (0, 0, -1, 0, 0, 0), (1, 0, 0, 0, 0, 0),
        (0, -1, 0, 0, 0, 0), (0.5, 0.2, 0.8, 0, 0, 0), (0, 0, 1, 0, 0, 120),
        (-1.3, 1, -1.4, -95, -176, 0),
    ]
    print("\nCasos para testar no Wokwi (ax ay az [g], gx gy gz [dps]) -> previsão int8:")
    case_preds = predict_tflite(int8_bytes, to_features(np.array(cases, dtype=np.float32)))
    for case, p in zip(cases, case_preds):
        print(f"  {str(case):<36} -> {LABELS[p]}")

    model_cc = os.path.join(OUT_DIR, "model.cc")
    with open(model_cc, "w", encoding="utf-8") as f:
        f.write(to_c_array(int8_bytes))
    shutil.copyfile(model_cc, MAIN_MODEL_CC)
    print(f"\nmodel.cc gerado ({len(int8_bytes)} bytes) e copiado para main/model.cc")


if __name__ == "__main__":
    main()
