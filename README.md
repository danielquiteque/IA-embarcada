# IA Embarcada e Modelos Compactos

Atividades práticas da UC **IA Embarcada e Modelos Compactos** (Pós-graduação em Inteligência Artificial Aplicada).
Hardware alvo: **ESP32-S3**, simulado no **Wokwi** e compilado com **ESP-IDF v5.5.5**.

| Atividade | Pasta | Conteúdo |
|---|---|---|
| 2/6 — Leitura de sensor | [atividade-2-leitura-sensor](atividade-2-leitura-sensor/) | Driver I2C em C para o MPU6050 (acelerômetro, giroscópio e temperatura) com leituras no monitor serial |

## Como compilar e simular

Pré-requisitos: ESP-IDF v5.5.5 (instalado com o EIM em `C:\esp\v5.5.5`) e a extensão **Wokwi Simulator** no VS Code.

```bat
:: compila um projeto (mostra a versão do ESP-IDF e roda idf.py build)
compilar.bat atividade-2-leitura-sensor

:: ou abre um terminal com o ESP-IDF carregado (idf.py disponível)
terminal-esp-idf.bat
```

Depois, abra a pasta da atividade no VS Code e rode `Ctrl+Shift+P` → **Wokwi: Start Simulator**.
A saída serial aparece no painel **Terminal → Wokwi Terminal**.
