"""
Modulo: gestor_unico.py
Descripcion: Implementa el patron Singleton para el gestor central del sistema
"""

import json
import datetime
from typing import Dict, List, Any, Optional

class GestorRedInteligente:
    """
    Clase Singleton que gestiona toda la red electrica inteligente
    Unica instancia en todo el sistema
    """
    
    _instancia_unica = None
    
    def __new__(cls):
        if cls._instancia_unica is None:
            cls._instancia_unica = super().__new__(cls)
            cls._instancia_unica._inicializado = False
        return cls._instancia_unica
    
    def __init__(self):
        if self._inicializado:
            return
        
        self._inicializado = True
        
        self.medidores = {}
        self.metricas_energeticas = {
            'potencia_total': 0.0,
            'potencia_solar_total': 0.0,
            'energia_consumida_hoy': 0.0,
            'energia_generada_hoy': 0.0,
            'muestras_totales': 0,
            'pico_maximo': 0.0,
            'pico_minimo': float('inf')
        }
        self.alertas = []
        self.tarifas_energeticas = {}
        self.esta_ejecutando = False
        self.historial_consumo = []
        
        print("Sistema de Redes Inteligentes INICIALIZADO")
        print(f"Fecha/Hora: {datetime.datetime.now()}")
        print("=" * 50)
    
    def registrar_medidor(self, id_medidor: str, datos_iniciales: Dict) -> bool:
        if id_medidor not in self.medidores:
            self.medidores[id_medidor] = {
                'id': id_medidor,
                'registrado_en': datetime.datetime.now(),
                'ultimos_datos': datos_iniciales,
                'historial': [datos_iniciales],
                'estado': 'ACTIVO',
                'tipo': datos_iniciales.get('tipo', 'RESIDENCIAL')
            }
            print(f"Medidor registrado: {id_medidor} ({self.medidores[id_medidor]['tipo']})")
            return True
        else:
            print(f"Medidor {id_medidor} ya existe en el sistema")
            return False
    
    def procesar_telemetria(self, id_medidor: str, datos: Dict) -> bool:
        if id_medidor not in self.medidores:
            self.registrar_medidor(id_medidor, datos)
        
        medidor = self.medidores[id_medidor]
        medidor['ultimos_datos'] = datos
        medidor['historial'].append(datos)
        
        self._actualizar_metricas_globales(datos)
        self._verificar_alertas(id_medidor, datos)
        
        costo = self._calcular_costo_instantaneo(datos)
        if costo:
            datos['costo_estimado'] = costo
        
        return True
    
    def _actualizar_metricas_globales(self, datos: Dict):
        metricas = datos.get('metricas', {})
        potencia = metricas.get('potencia_activa_kW', 0)
        solar = metricas.get('generacion_solar_kW', 0)
        
        self.metricas_energeticas['potencia_total'] += potencia
        self.metricas_energeticas['potencia_solar_total'] += solar
        self.metricas_energeticas['muestras_totales'] += 1
        
        if potencia > self.metricas_energeticas['pico_maximo']:
            self.metricas_energeticas['pico_maximo'] = potencia
        if potencia < self.metricas_energeticas['pico_minimo']:
            self.metricas_energeticas['pico_minimo'] = potencia
        
        self.metricas_energeticas['energia_consumida_hoy'] += potencia * 0.000833
        self.metricas_energeticas['energia_generada_hoy'] += solar * 0.000833
    
    def _verificar_alertas(self, id_medidor: str, datos: Dict):
        metricas = datos.get('metricas', {})
        potencia = metricas.get('potencia_activa_kW', 0)
        voltaje = metricas.get('voltaje_V', 0)
        frecuencia = metricas.get('frecuencia_Hz', 60)
        
        if potencia > 20.0:
            self.alertas.append({
                'timestamp': datetime.datetime.now(),
                'id_medidor': id_medidor,
                'tipo': 'ALTO_CONSUMO',
                'valor': potencia,
                'umbral': 20.0,
                'gravedad': 'ALTA',
                'mensaje': f"Consumo excesivo: {potencia:.2f} kW"
            })
            print(f"ALERTA: Consumo alto en {id_medidor}: {potencia:.2f} kW")
        
        if voltaje < 115 or voltaje > 125:
            self.alertas.append({
                'timestamp': datetime.datetime.now(),
                'id_medidor': id_medidor,
                'tipo': 'VOLTAJE_ANORMAL',
                'valor': voltaje,
                'umbral': '115-125V',
                'gravedad': 'MEDIA',
                'mensaje': f"Voltaje fuera de rango: {voltaje:.2f} V"
            })
            print(f"ALERTA: Voltaje anormal en {id_medidor}: {voltaje:.2f} V")
        
        if frecuencia < 59.9 or frecuencia > 60.1:
            self.alertas.append({
                'timestamp': datetime.datetime.now(),
                'id_medidor': id_medidor,
                'tipo': 'FRECUENCIA_INESTABLE',
                'valor': frecuencia,
                'umbral': '59.9-60.1 Hz',
                'gravedad': 'BAJA',
                'mensaje': f"Frecuencia inestable: {frecuencia:.2f} Hz"
            })
            print(f"ALERTA: Frecuencia inestable en {id_medidor}: {frecuencia:.2f} Hz")
    
    def _calcular_costo_instantaneo(self, datos: Dict) -> Optional[float]:
        hora = datos.get('hora_simulada', '00:00')
        try:
            hora_num = int(hora.split(':')[0])
        except:
            hora_num = 0
        
        if 18 <= hora_num <= 22:
            tarifa = 450
        elif 7 <= hora_num <= 9:
            tarifa = 350
        elif 1 <= hora_num <= 5:
            tarifa = 200
        else:
            tarifa = 280
        
        potencia = datos.get('metricas', {}).get('potencia_activa_kW', 0)
        costo_por_hora = potencia * tarifa
        costo_instantaneo = (costo_por_hora / 60) / 60
        
        return round(costo_instantaneo, 2)
    
    def obtener_estado_sistema(self) -> Dict:
        return {
            'total_medidores': len(self.medidores),
            'total_muestras': self.metricas_energeticas['muestras_totales'],
            'potencia_total_kW': round(self.metricas_energeticas['potencia_total'], 2),
            'potencia_solar_kW': round(self.metricas_energeticas['potencia_solar_total'], 2),
            'energia_consumida_kWh': round(self.metricas_energeticas['energia_consumida_hoy'], 3),
            'energia_generada_kWh': round(self.metricas_energeticas['energia_generada_hoy'], 3),
            'pico_maximo_kW': round(self.metricas_energeticas['pico_maximo'], 2),
            'pico_minimo_kW': round(self.metricas_energeticas['pico_minimo'], 2),
            'alertas_activas': len([a for a in self.alertas if a.get('resuelta', False) is False]),
            'esta_ejecutando': self.esta_ejecutando,
            'medidores_activos': len([m for m in self.medidores.values() if m['estado'] == 'ACTIVO'])
        }
    
    def obtener_medidor(self, id_medidor: str) -> Optional[Dict]:
        return self.medidores.get(id_medidor)
    
    def obtener_alertas(self, solo_activas: bool = True) -> List[Dict]:
        if solo_activas:
            return [a for a in self.alertas if not a.get('resuelta', False)]
        return self.alertas
    
    def iniciar(self):
        self.esta_ejecutando = True
        print("Sistema de Redes Inteligentes INICIADO")
        print(f"Monitoreando {len(self.medidores)} medidores")
    
    def detener(self):
        self.esta_ejecutando = False
        print("Sistema de Redes Inteligentes DETENIDO")
        print(f"Resumen: {self.metricas_energeticas['muestras_totales']} muestras procesadas")
    
    def generar_reporte(self) -> str:
        estado = self.obtener_estado_sistema()
        reporte = f"""

        REPORTE DEL SISTEMA 

        Fecha: {datetime.datetime.now()}
        
        ESTADISTICAS GENERALES:
        - Medidores: {estado['total_medidores']}
        - Muestras procesadas: {estado['total_muestras']}
        - Potencia total: {estado['potencia_total_kW']} kW
        - Generacion solar: {estado['potencia_solar_kW']} kW
        
        CONSUMO:
        - Energia consumida: {estado['energia_consumida_kWh']} kWh
        - Energia generada: {estado['energia_generada_kWh']} kWh
        - Pico maximo: {estado['pico_maximo_kW']} kW
        - Pico minimo: {estado['pico_minimo_kW']} kW
        
        ALERTAS ACTIVAS: {estado['alertas_activas']}
        """
        return reporte