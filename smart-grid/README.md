## Sistema de Redes Inteligentes SmartGrid

>Brayan Stiven Plata Sandoval

>Juan Felipe Velasco Tobon

>Link Video Semana-3
>https://youtu.be/xaHxhgXt6jY
>Link Video Semana-4
>https://youtu.be/DETsGKiOHws



##  Tecnologías utilizadas

- **Lenguaje:** Python
- **Framework de interfaz:** Streamlit
- **Librerías:** Pandas, Threading
- **Patrones de diseño implementados:** Singleton, Factory

##  Interfaz de demostración Smart Grid

<img width="1352" height="646" alt="image" src="https://github.com/user-attachments/assets/87418ec8-6a0c-4cb3-a9d7-d4612e64fd9b" />

## Smart Grid — Guía de Instalación y Ejecución
Este documento explica paso a paso cómo instalar y ejecutar el proyecto Smart Grid (Sistema de Gestión de Redes Inteligentes) en tu computadora.

📋 Requisitos Previos
Antes de comenzar, asegúrate de tener instalado:

Python 3.10 o superior (recomendado 3.10, 3.11 o 3.12).

Un editor de código o terminal (VS Code, CMD, PowerShell, etc.).

¿Cómo verificar si tienes Python instalado?
Abre una terminal (CMD o PowerShell) y escribe:

bash
python --version
Si el comando responde con algo como Python 3.11.5, ¡estás listo! Si dice que no se reconoce el comando, necesitas descargar e instalar Python desde python.org. Importante: Al instalar Python, marca la casilla "Add Python to PATH".

## Pasos para la Instalación
1. Abrir la terminal en la carpeta del proyecto
Abre tu terminal y navega hasta la carpeta donde descargaste el proyecto. Por ejemplo:

bash
**cd C:\Users\TuUsuario\Desktop\smart-grid**
(Asegúrate de que estás en la carpeta que contiene el archivo main.py y streamlit_app.py).

2. Instalar las dependencias
El proyecto requiere Streamlit (para la interfaz gráfica) y Pandas (para el manejo de tablas). Ejecuta el siguiente comando:

bash
**python -m pip install streamlit pandas**
Este comando descargará e instalará automáticamente todo lo necesario. Espera a que termine (verás un mensaje de "Successfully installed...").

▶️ Cómo Ejecutar el Proyecto
Opción A: Interfaz Gráfica (Streamlit) — Recomendado
Para abrir el panel de operación visual y hacer las simulaciones:

bash
**python -m streamlit run streamlit_app.py**
¿Qué sucede?
Se abrirá automáticamente una pestaña en tu navegador web (normalmente en http://localhost:8501) con la interfaz del Smart Grid. Desde allí podrás modificar las fuentes de energía, cambiar el esquema tarifario, ver la topología de la red y descargar los resultados.

## Opción B: Simulación por Consola (Terminal)
Si prefieres ver los resultados directamente en la terminal sin interfaz gráfica, ejecuta:

bash
**python main.py**
¿Qué sucede?
El sistema simulará las 24 horas del día y te mostrará en la consola los picos de demanda, las alertas de voltaje, el balance de carga y el costo total de la facturación.

## Cómo Ejecutar las Pruebas
Si deseas verificar que los patrones de diseño (Singleton, Factory, Adapter, etc.) están funcionando correctamente, puedes ejecutar las pruebas unitarias:

bash
python -m tests.test_patterns
python -m tests.test_structural_patterns
python -m tests.test_structural_patterns_extended
Cada comando imprimirá varios mensajes OK: confirmando que las pruebas pasaron.
