# Atividade Avaliativa Prática 2/6 — Leitura de sensor

Aplicação em C com ESP-IDF que lê um **MPU6050** (acelerômetro + giroscópio + temperatura) via I2C
em um **ESP32-S3** simulado no **Wokwi**, imprimindo as leituras no monitor serial a cada 500 ms.

## Circuito (`diagram.json`)

| MPU6050 | ESP32-S3 DevKitC-1 |
|---------|--------------------|
| VCC     | 3V3                |
| GND     | GND                |
| SDA     | GPIO 8             |
| SCL     | GPIO 9             |

AD0 fica desconectado (nível baixo) → endereço I2C `0x68`.

## Estrutura

```
├── CMakeLists.txt        # projeto ESP-IDF
├── sdkconfig.defaults    # target esp32s3
├── diagram.json          # circuito do Wokwi
├── wokwi.toml            # aponta o Wokwi para o firmware gerado em build/
└── main/
    ├── main.c            # app_main: inicializa o sensor e lê em loop
    ├── mpu6050.h         # registradores, escalas e API do driver
    └── mpu6050.c         # driver I2C (driver/i2c_master.h do ESP-IDF ≥ 5.3)
```

## Como o código funciona

1. `mpu6050_init()` cria o barramento I2C (`i2c_new_master_bus`), registra o dispositivo em 400 kHz,
   lê o registrador `WHO_AM_I` (0x75) para confirmar que o sensor responde com `0x68`, escreve `0x00`
   em `PWR_MGMT_1` (0x6B) para tirá-lo do modo sleep e configura as faixas ±2 g / ±250 °/s.
2. `mpu6050_read()` lê 14 bytes a partir de `ACCEL_XOUT_H` (0x3B) numa só transação e converte:
   - aceleração: `raw / 16384` → g
   - giroscópio: `raw / 131` → °/s
   - temperatura: `raw / 340 + 36.53` → °C
3. Todas as funções retornam `esp_err_t`; erros de inicialização param o programa com `ESP_ERROR_CHECK`
   e falhas de leitura geram um `ESP_LOGW` sem derrubar a aplicação.

## Como executar (VS Code + ESP-IDF + Wokwi)

1. Abra esta pasta no VS Code com as extensões **ESP-IDF** e **Wokwi Simulator** instaladas
   (a licença do Wokwi é ativada pelo comando `Wokwi: Request a New License`).
2. Selecione o target **esp32s3** e clique em **Build** (ou `idf.py build` no terminal do ESP-IDF).
3. Abra `diagram.json` e clique em ▶ (ou `F1` → `Wokwi: Start Simulator`).
4. Clique no MPU6050 durante a simulação para mudar aceleração/rotação/temperatura e veja os valores mudarem.

Saída esperada no monitor serial:

```
I (xxx) mpu6050: MPU6050 encontrado (WHO_AM_I = 0x68)
I (xxx) app: Acel[g] x=  0.00 y=  0.00 z=  1.00 | Giro[dps] x=   0.00 y=   0.00 z=   0.00 | Temp=24.00 C
```

## Entrega — screenshots

Salvar em `docs/`:
- [ ] Configuração do ESP-IDF e da conta Wokwi
- [ ] Circuito montado no Wokwi
- [ ] Build compilando sem erros
- [ ] Monitor serial mostrando as leituras
