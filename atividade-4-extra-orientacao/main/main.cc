// Classificação de orientação e movimento com MPU6050 + TFLite Micro no ESP32-S3.
// Pipeline: leitura I2C -> normalização -> quantização int8 -> inferência -> classe.

#include <cmath>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"

#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include "model.h"
#include "mpu6050.h"

namespace {

const char *TAG = "orientacao";

// Pinos I2C do ESP32-S3 ligados ao MPU6050 (ver diagram.json)
constexpr gpio_num_t kSdaPin = GPIO_NUM_8;
constexpr gpio_num_t kSclPin = GPIO_NUM_9;
constexpr int kPeriodMs = 500;

// Devem coincidir com train/train_orientacao.py
constexpr int kNumFeatures = 6;       // ax, ay, az [g], gx, gy, gz [dps / kGyroScale]
constexpr float kGyroScale = 250.0f;  // fundo de escala do giroscópio (±250 °/s)
constexpr int kNumClasses = 7;
const char *const kLabels[kNumClasses] = {
    "plana, face para cima",    // Z+
    "plana, face para baixo",   // Z-
    "em pe, eixo X para cima",  // X+
    "em pe, eixo X para baixo", // X-
    "de lado, eixo Y para cima",  // Y+
    "de lado, eixo Y para baixo", // Y-
    "em rotacao",
};

constexpr int kTensorArenaSize = 4 * 1024;
alignas(16) uint8_t tensor_arena[kTensorArenaSize];

// Quantização com arredondamento e saturação (melhoria em relação ao Hello World)
int8_t Quantize(float value, const TfLiteTensor *tensor)
{
    int32_t q = static_cast<int32_t>(lroundf(value / tensor->params.scale)) + tensor->params.zero_point;
    if (q < -128) q = -128;
    if (q > 127) q = 127;
    return static_cast<int8_t>(q);
}

float Dequantize(int8_t value, const TfLiteTensor *tensor)
{
    return (value - tensor->params.zero_point) * tensor->params.scale;
}

}  // namespace

extern "C" void app_main(void)
{
    static mpu6050_t mpu;
    ESP_ERROR_CHECK(mpu6050_init(&mpu, kSdaPin, kSclPin));

    const tflite::Model *model = tflite::GetModel(g_model);
    if (model->version() != TFLITE_SCHEMA_VERSION) {
        ESP_LOGE(TAG, "Schema do modelo %lu diferente do suportado %d",
                 static_cast<unsigned long>(model->version()), TFLITE_SCHEMA_VERSION);
        return;
    }

    // O modelo usa apenas FullyConnected (com ReLU fundido) e Softmax
    static tflite::MicroMutableOpResolver<2> resolver;
    resolver.AddFullyConnected();
    resolver.AddSoftmax();

    static tflite::MicroInterpreter interpreter(model, resolver, tensor_arena, kTensorArenaSize);
    if (interpreter.AllocateTensors() != kTfLiteOk) {
        ESP_LOGE(TAG, "AllocateTensors() falhou");
        return;
    }
    TfLiteTensor *input = interpreter.input(0);
    TfLiteTensor *output = interpreter.output(0);
    ESP_LOGI(TAG, "Modelo: %d bytes | Tensor arena: %u de %d bytes usados",
             g_model_len, static_cast<unsigned>(interpreter.arena_used_bytes()), kTensorArenaSize);

    while (true) {
        mpu6050_data_t d;
        if (mpu6050_read(&mpu, &d) != ESP_OK) {
            ESP_LOGW(TAG, "Leitura do sensor falhou");
            vTaskDelay(pdMS_TO_TICKS(kPeriodMs));
            continue;
        }

        const float features[kNumFeatures] = {
            d.accel_g[0], d.accel_g[1], d.accel_g[2],
            d.gyro_dps[0] / kGyroScale, d.gyro_dps[1] / kGyroScale, d.gyro_dps[2] / kGyroScale,
        };
        for (int i = 0; i < kNumFeatures; i++) {
            input->data.int8[i] = Quantize(features[i], input);
        }

        const int64_t start_us = esp_timer_get_time();
        if (interpreter.Invoke() != kTfLiteOk) {
            ESP_LOGE(TAG, "Invoke() falhou");
            vTaskDelay(pdMS_TO_TICKS(kPeriodMs));
            continue;
        }
        const int64_t elapsed_us = esp_timer_get_time() - start_us;

        int best = 0;
        for (int c = 1; c < kNumClasses; c++) {
            if (output->data.int8[c] > output->data.int8[best]) best = c;
        }
        const float confidence = Dequantize(output->data.int8[best], output);

        ESP_LOGI(TAG, "Acel[g] %5.2f %5.2f %5.2f | Giro[dps] %6.1f %6.1f %6.1f -> %s (%.0f%%) [%lld us]",
                 d.accel_g[0], d.accel_g[1], d.accel_g[2],
                 d.gyro_dps[0], d.gyro_dps[1], d.gyro_dps[2],
                 kLabels[best], confidence * 100.0f, elapsed_us);

        vTaskDelay(pdMS_TO_TICKS(kPeriodMs));
    }
}
