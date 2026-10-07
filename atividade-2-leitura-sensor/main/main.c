#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

#include "mpu6050.h"

// Pinos I2C do ESP32-S3 ligados ao MPU6050 (ver diagram.json)
#define I2C_SDA_PIN     GPIO_NUM_8
#define I2C_SCL_PIN     GPIO_NUM_9
#define READ_PERIOD_MS  500

static const char *TAG = "app";

void app_main(void)
{
    static mpu6050_t mpu;
    ESP_ERROR_CHECK(mpu6050_init(&mpu, I2C_SDA_PIN, I2C_SCL_PIN));

    while (1) {
        mpu6050_data_t d;
        esp_err_t err = mpu6050_read(&mpu, &d);
        if (err == ESP_OK) {
            ESP_LOGI(TAG, "Acel[g] x=%6.2f y=%6.2f z=%6.2f | Giro[dps] x=%7.2f y=%7.2f z=%7.2f | Temp=%5.2f C",
                     d.accel_g[0], d.accel_g[1], d.accel_g[2],
                     d.gyro_dps[0], d.gyro_dps[1], d.gyro_dps[2],
                     d.temp_c);
        } else {
            ESP_LOGW(TAG, "Leitura falhou: %s", esp_err_to_name(err));
        }
        vTaskDelay(pdMS_TO_TICKS(READ_PERIOD_MS));
    }
}
