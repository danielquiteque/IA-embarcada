#pragma once

#include "esp_err.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"

#ifdef __cplusplus
extern "C" {
#endif

// Endereço I2C do MPU6050 com o pino AD0 em nível baixo
#define MPU6050_I2C_ADDR        0x68
#define MPU6050_I2C_FREQ_HZ     400000

// Registradores usados (datasheet MPU-6000/6050, Register Map rev 4.2)
#define MPU6050_REG_GYRO_CONFIG  0x1B
#define MPU6050_REG_ACCEL_CONFIG 0x1C
#define MPU6050_REG_ACCEL_XOUT_H 0x3B
#define MPU6050_REG_PWR_MGMT_1   0x6B
#define MPU6050_REG_WHO_AM_I     0x75

// Fatores de escala para as faixas padrão (±2 g e ±250 °/s)
#define MPU6050_ACCEL_LSB_PER_G   16384.0f
#define MPU6050_GYRO_LSB_PER_DPS  131.0f

typedef struct {
    i2c_master_bus_handle_t bus;
    i2c_master_dev_handle_t dev;
} mpu6050_t;

typedef struct {
    float accel_g[3];   // x, y, z em g
    float gyro_dps[3];  // x, y, z em graus/s
    float temp_c;       // temperatura interna em °C
} mpu6050_data_t;

// Cria o barramento I2C, registra o sensor, confere o WHO_AM_I e tira o chip do modo sleep.
esp_err_t mpu6050_init(mpu6050_t *mpu, gpio_num_t sda, gpio_num_t scl);

// Lê os 14 bytes de acelerômetro, temperatura e giroscópio em uma única transação.
esp_err_t mpu6050_read(mpu6050_t *mpu, mpu6050_data_t *out);

#ifdef __cplusplus
}
#endif
