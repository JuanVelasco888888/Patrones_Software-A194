"""
Modulo: simulador_medidor.py
Descripcion: Simula un medidor inteligente de energia
"""

import time
import json
import random
import datetime
from typing import Dict
import paho.mqtt.client as mqtt

from nucleo.gestor_unico import GestorRedInteligente

class SimuladorMedidorInteligente:
    
    def __init__(self, id_medidor: str, 
                 broker_url: str = "broker.hivemq.com",
                 broker_puerto: int = 1883,
                 tipo_medidor: str = "RESIDENCIAL"):
        
        self.id_medidor = id_medidor
        self.broker_url = broker_url
        self.broker_puerto = broker_puerto
        self.tipo_medidor = tipo_medidor
        self.topico = f"red_inteligente/medidores/{id_medidor}/telemetria"
        self.cliente_mqtt = None
        self.esta_ejecutando = False
        
        self.gestor = GestorRedInteligente()
        
        self.configuracion = {
            'RESIDENCIAL': {
                'consumo_base': 8.0,
                'pico_alto': 20.0,
                'solar_maximo': 4.5,
                'bateria_capacidad': 10.0
            },
            'INDUSTRIAL': {
                'consumo_base': 45.0,
                'pico_alto': 85.0,
                'solar_maximo': 25.0,
                'bateria_capacidad': 50.0
            },
            'COMERCIAL': {
                'consumo_base': 25.0,
                'pico_alto': 50.0,
                'solar_maximo': 12.0,
                'bateria_capacidad': 20.0
            }
        }
    
    def _generar_telemetria(self, hora_simulada: int) -> Dict:
        conf = self.configuracion[self.tipo_medidor]
        
        voltaje = round(random.uniform(117.5, 122.5), 2)
        
        if 18 <= hora_simulada <= 22:
            corriente_base = random.uniform(conf['pico_alto'] * 0.7, conf['pico_alto'])
        elif 7 <= hora_simulada <= 9:
            corriente_base = random.uniform(conf['consumo_base'] * 0.6, conf['consumo_base'] * 1.2)
        elif 1 <= hora_simulada <= 5:
            corriente_base = random.uniform(conf['consumo_base'] * 0.2, conf['consumo_base'] * 0.4)
        else:
            corriente_base = random.uniform(conf['consumo_base'] * 0.5, conf['consumo_base'] * 0.9)
        
        corriente = round(corriente_base, 2)
        factor_potencia = 0.95
        potencia_activa_kW = round((voltaje * corriente * factor_potencia) / 1000, 3)
        
        generacion_solar_kW = 0.0
        if 6 <= hora_simulada <= 18:
            factor_pico = 1.0 - (abs(12 - hora_simulada) / 6.0)
            generacion_solar_kW = round(
                random.uniform(conf['solar_maximo'] * 0.3, conf['solar_maximo']) * max(0, factor_pico), 
                3
            )
        
        bateria_soc = round(random.uniform(40.0, 95.0), 1)
        potencia_neta_kW = round(potencia_activa_kW - generacion_solar_kW, 3)
        estado_red = "CONSUMIENDO" if potencia_neta_kW >= 0 else "INYECTANDO"
        frecuencia_Hz = round(random.uniform(59.95, 60.05), 2)
        temperatura_c = round(random.uniform(20.0, 45.0), 1)
        
        return {
            "id_dispositivo": self.id_medidor,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "hora_simulada": f"{hora_simulada:02d}:00",
            "tipo_medidor": self.tipo_medidor,
            "metricas": {
                "voltaje_V": voltaje,
                "corriente_A": corriente,
                "potencia_activa_kW": potencia_activa_kW,
                "generacion_solar_kW": generacion_solar_kW,
                "potencia_neta_kW": abs(potencia_neta_kW),
                "frecuencia_Hz": frecuencia_Hz,
                "bateria_SoC_pct": bateria_soc,
                "temperatura_C": temperatura_c
            },
            "estado_red": estado_red,
            "tipo_consumo": self.tipo_medidor
        }
    
    def iniciar(self):
        self.esta_ejecutando = True
        self.gestor.iniciar()
        
        datos_iniciales = self._generar_telemetria(6)
        self.gestor.registrar_medidor(self.id_medidor, datos_iniciales)
        
        self.cliente_mqtt = mqtt.Client(client_id=f"Sim_{self.id_medidor}")
        self.cliente_mqtt.connect(self.broker_url, self.broker_puerto, 60)
        self.cliente_mqtt.loop_start()
        
        print(f"\n{'='*50}")
        print(f"SIMULADOR INICIADO: {self.id_medidor}")
        print(f"Tipo: {self.tipo_medidor}")
        print(f"Publicando en: {self.topico}")
        print(f"Broker: {self.broker_url}:{self.broker_puerto}")
        print(f"{'='*50}\n")
        
        hora_simulada = 6
        
        try:
            while self.esta_ejecutando:
                datos = self._generar_telemetria(hora_simulada)
                payload_json = json.dumps(datos)
                
                resultado = self.cliente_mqtt.publish(self.topico, payload_json)
                
                if resultado.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.gestor.procesar_telemetria(self.id_medidor, datos)
                    print(f"[{datos['timestamp']}] Hora: {datos['hora_simulada']} | "
                          f"Consumo: {datos['metricas']['potencia_activa_kW']:.2f} kW | "
                          f"Solar: {datos['metricas']['generacion_solar_kW']:.2f} kW | "
                          f"Estado: {datos['estado_red']} | "
                          f"Temp: {datos['metricas']['temperatura_C']} C")
                else:
                    print(f"Error al publicar datos: {resultado.rc}")
                
                hora_simulada = (hora_simulada + 1) % 24
                time.sleep(3)
                
        except KeyboardInterrupt:
            self.detener()
    
    def detener(self):
        self.esta_ejecutando = False
        self.gestor.detener()
        
        if self.cliente_mqtt:
            self.cliente_mqtt.loop_stop()
            self.cliente_mqtt.disconnect()
        
        print(f"\nSimulador {self.id_medidor} DETENIDO")