# Relatório — Hello World com TensorFlow Lite Micro no ESP32-S3 (Wokwi)

**Disciplina:** IA Embarcada e Modelos Compactos — Atividade Avaliativa Prática 4/6

## 1. Objetivo

Reproduzir o exemplo *Hello World* do TFLite Micro: treinar uma rede neural que aproxima `sin(x)` no
intervalo [0, 2π], comprimi-la por quantização int8, convertê-la em um array C e executá-la em um
ESP32-S3 simulado no Wokwi, analisando o código e a documentação do exemplo.

## 2. Passos reproduzidos

| Etapa | O que foi feito |
|---|---|
| Dataset | 1000 valores `x ~ U(0, 2π)` e `y = sin(x)`; 20% para validação |
| Treino | Keras `Dense(32, relu) → Dense(32, relu) → Dense(1)`, Adam, MSE, 300 épocas, batch 64 |
| Conversão float | `TFLiteConverter.from_keras_model` → `hello_world_float.tflite` |
| Quantização | Pós-treino *full integer* a partir do SavedModel, com dataset representativo de 500 amostras, entrada/saída int8 → `hello_world_int8.tflite` |
| Array C | `.tflite` → `model.cc` (equivalente ao `xxd -i`) com `alignas(8)` |
| Firmware | Exemplo `hello_world` do esp-tflite-micro 1.4.1, compilado com ESP-IDF para esp32s3 |
| Simulação | Wokwi com `diagram.json` + `wokwi.toml` apontando para `build/` |

## 3. Resultados do modelo

Avaliação em 200 pontos igualmente espaçados em [0, 2π]:

| Modelo | Tamanho | MAE | RMSE |
|---|---|---|---|
| float32 | 6580 B | 0.0124 | 0.0205 |
| int8 | 5160 B | 0.0191 | 0.0253 |
| Original do exemplo (16 → 16 → 1, int8) | 2488 B | — | — |

Parâmetros de quantização do modelo gerado (lidos do flatbuffer):

- entrada: `scale = 0.02463`, `zero_point = -128` → o int8 [-128, 127] cobre x ∈ [0, 6.28]
- saída: `scale = 0.00788`, `zero_point = -2` → cobre y ≈ [-0.99, 1.02]
- 3 operadores, todos `FULLY_CONNECTED` (o ReLU fica fundido na própria camada)

## 4. Análise do código

**`main.cc`** — ponto de entrada `app_main()` (em `extern "C"`, pois o ESP-IDF chama uma função C).
Segue o padrão Arduino: `setup()` uma vez e `loop()` a cada 500 ms via `vTaskDelay`, cedendo a CPU
ao FreeRTOS entre inferências.

**`main_functions.cc`** — a pipeline do TFLite Micro:

1. `tflite::GetModel(g_model)` mapeia o array em memória sem copiar nem fazer parse (flatbuffer), e a
   versão do schema é conferida.
2. `MicroMutableOpResolver<1>` registra **só** o operador `FullyConnected`. Em MCU não se linka o
   conjunto completo de operadores: cada op registrado ocupa flash.
3. `MicroInterpreter` recebe um `tensor_arena` estático de 2000 bytes. Não há `malloc`: todos os
   tensores intermediários são alocados dentro desse buffer por `AllocateTensors()`. Adicionei um
   `MicroPrintf` com `arena_used_bytes()` para medir o quanto é de fato usado.
4. Em `loop()`, `x` percorre [0, 2π] em `kInferencesPerCycle = 20` passos. A entrada é **quantizada**
   (`x / scale + zero_point`), `Invoke()` roda a inferência e a saída é **desquantizada**
   (`(y_q - zero_point) * scale`) antes de ser impressa.

**`output_handler.cc`** — isola a saída (aqui `MicroPrintf` no serial) para que cada placa possa ter
a sua implementação (LED, display, PWM) sem mexer na pipeline.

**`model.cc` / `model.h`** — o `.tflite` vira um `const unsigned char[]`, que vai para a **flash**
(rodata) e não ocupa RAM. Os bytes 4–7 são `TFL3`, o identificador do formato. O `alignas(8)` evita
acessos desalinhados ao ler os campos do flatbuffer.

## 5. Observações

1. **Wokwi e ESP-NN.** O componente compila com `-DESP_NN`, que usa kernels otimizados com instruções
   SIMD do ESP32-S3 que o Wokwi não simula. Para rodar foi preciso remover essa flag (na aula,
   comentando a linha no `CMakeLists.txt` do componente; aqui, removendo-a no `CMakeLists.txt` do
   projeto para não editar código de terceiros). No hardware real, manter o ESP-NN acelera bastante a
   inferência. Em versões mais novas do esp-tflite-micro isso virou a opção Kconfig
   `ESP_TFLITE_MICRO_USE_ESP_NN`.
2. **Quantização reduziu pouco o tamanho total (−22%).** Os pesos ficam 4× menores (float32 → int8),
   mas o modelo tem só ~1,1 mil parâmetros, então o cabeçalho e os metadados do flatbuffer (nomes de
   tensores, assinaturas) pesam proporcionalmente muito. Em modelos maiores o ganho tende a ~4×.
3. **Perda de precisão pequena.** O MAE subiu de 0.012 para 0.019, aceitável para a aplicação e em
   troca de aritmética inteira, que é mais rápida e econômica no MCU.
4. **Treino não determinístico.** Na primeira execução, mesmo com seed fixa, a rede convergiu mal
   (MAE ≈ 0.29), provavelmente por neurônios ReLU "mortos"; ao repetir, chegou a 0.012. Por isso vale
   sempre avaliar o `.tflite` final antes de embarcar.
5. **Quantização da entrada sem arredondamento nem saturação.** `int8_t x_q = x / scale + zp` trunca
   em vez de arredondar e não limita a [-128, 127]. Funciona aqui porque x nunca sai de [0, 2π], mas
   para dados reais de sensor seria melhor usar `roundf` e saturar o valor.
6. **Tamanho da arena.** Os 2000 bytes são fixados manualmente. O valor medido com
   `arena_used_bytes()` mostra a folga, e na prática ajusta-se a arena a esse valor mais uma margem.
7. **Este modelo é maior que o original** (32 neurônios por camada no notebook contra 16 no exemplo),
   mas ainda cabe com sobra: ~5 KB de flash e RAM dentro da arena de 2000 bytes.

## 6. Evidência

Print do Wokwi rodando: `docs/wokwi-hello-world.png`
