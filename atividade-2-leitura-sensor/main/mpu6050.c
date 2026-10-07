#include "mpu6050.h"

#include "esp_check.h"
#include "esp_log.h"

#define I2C_TIMEOUT_MS 100

static const char *TAG = "mpu6050";

static esp_err_t write_reg(mpu6050_t *mpu, uint8_t reg, uint8_t value)
{
    uint8_t buf[2] = {reg, value};
    return i2c_master_transmit(mpu->dev, buf, sizeof(buf), I2C_TIMEOUT_MS);
}

static esp_err_t read_regs(mpu6050_t *mpu, uint8_t reg, uint8_t *data, size_t len)
{
    return i2c_master_transmit_receive(mpu->dev, &reg, 1, data, len, I2C_TIMEOUT_MS);
}

esp_err_t mpu6050_init(mpu6050_t *mpu, gpio_num_t sda, gpio_num_t scl)
{
    i2c_master_bus_config_t bus_cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = sda,
        .scl_io_num = scl,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_RETURN_ON_ERROR(i2c_new_master_bus(&bus_cfg, &mpu->bus), TAG, "falha ao criar barramento I2C");

    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = MPU6050_I2C_ADDR,
        .scl_speed_hz = MPU6050_I2C_FREQ_HZ,
    };
    ESP_RETURN_ON_ERROR(i2c_master_bus_add_device(mpu->bus, &dev_cfg, &mpu->dev), TAG, "falha ao adicionar MPU6050");

    uint8_t who_am_i = 0;
    ESP_RETURN_ON_ERROR(read_regs(mpu, MPU6050_REG_WHO_AM_I, &who_am_i, 1), TAG, "sensor não responde no I2C");
    if (who_am_i != MPU6050_I2C_ADDR) {
        ESP_LOGE(TAG, "WHO_AM_I inesperado: 0x%02X", who_am_i);
        return ESP_ERR_NOT_FOUND;
    }
    ESP_LOGI(TAG, "MPU6050 encontrado (WHO_AM_I = 0x%02X)", who_am_i);

    // O chip inicia em sleep: zerar PWR_MGMT_1 acorda e usa o oscilador interno
    ESP_RETURN_ON_ERROR(write_reg(mpu, MPU6050_REG_PWR_MGMT_1, 0x00), TAG, "falha ao acordar sensor");
    ESP_RETURN_ON_ERROR(write_reg(mpu, MPU6050_REG_ACCEL_CONFIG, 0x00), TAG, "falha ao configurar acelerômetro");
    ESP_RETURN_ON_ERROR(write_reg(mpu, MPU6050_REG_GYRO_CONFIG, 0x00), TAG, "falha ao configurar giroscópio");
    return ESP_OK;
}

esp_err_t mpu6050_read(mpu6050_t *mpu, mpu6050_data_t *out)
{
    // Ordem: ACCEL_X/Y/Z, TEMP, GYRO_X/Y/Z, cada um com 16 bits big-endian
    uint8_t raw[14];
    ESP_RETURN_ON_ERROR(read_regs(mpu, MPU6050_REG_ACCEL_XOUT_H, raw, sizeof(raw)), TAG, "falha na leitura");

    int16_t v[7];
    for (int i = 0; i < 7; i++) {
        v[i] = (int16_t)((raw[2 * i] << 8) | raw[2 * i + 1]);
    }

    for (int axis = 0; axis < 3; axis++) {
        out->accel_g[axis] = v[axis] / MPU6050_ACCEL_LSB_PER_G;
        out->gyro_dps[axis] = v[4 + axis] / MPU6050_GYRO_LSB_PER_DPS;
    }
    out->temp_c = v[3] / 340.0f + 36.53f;
    return ESP_OK;
}
