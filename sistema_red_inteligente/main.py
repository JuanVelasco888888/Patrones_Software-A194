"""
Archivo: main.py
Descripcion: Punto de entrada del Sistema de Redes Inteligentes
"""

import sys
import time
import threading
from nucleo.gestor_unico import GestorRedInteligente
from nucleo.simulador_medidor import SimuladorMedidorInteligente

def mostrar_banner():
    banner = """
    ==================================================
    SISTEMA DE GESTION DE REDES INTELIGENTES
    ==================================================
    Monitoreo en tiempo real
    Integracion con energias renovables
    Balanceo de carga inteligente
    Facturacion dinamica
    ==================================================
    """
    print(banner)

def menu_principal():
    print("\n" + "="*50)
    print("OPCIONES DEL SISTEMA")
    print("="*50)
    print("1. Iniciar simulacion con multiples medidores")
    print("2. Ver estado del sistema")
    print("3. Ver alertas activas")
    print("4. Generar reporte")
    print("5. Probar singleton (verificar instancia unica)")
    print("6. Salir")
    print("="*50)

def iniciar_sistema():
    gestor = GestorRedInteligente()
    
    medidores = [
        SimuladorMedidorInteligente("MEDIDOR_CASA_01", tipo_medidor="RESIDENCIAL"),
        SimuladorMedidorInteligente("MEDIDOR_CASA_02", tipo_medidor="RESIDENCIAL"),
        SimuladorMedidorInteligente("MEDIDOR_FABRICA_01", tipo_medidor="INDUSTRIAL"),
        SimuladorMedidorInteligente("MEDIDOR_OFICINA_01", tipo_medidor="COMERCIAL"),
    ]
    
    print("\nINICIANDO SISTEMA CON MULTIPLES MEDIDORES")
    print(f"Total de medidores: {len(medidores)}")
    print("="*50)
    
    hilos = []
    for medidor in medidores:
        hilo = threading.Thread(target=medidor.iniciar, daemon=True)
        hilo.start()
        hilos.append(hilo)
        time.sleep(0.5)
    
    try:
        while True:
            menu_principal()
            opcion = input("\nSeleccione una opcion: ")
            
            if opcion == "1":
                print("\nEl sistema ya esta en ejecucion...")
            elif opcion == "2":
                estado = gestor.obtener_estado_sistema()
                print("\nESTADO DEL SISTEMA:")
                print(f"   Medidores totales: {estado['total_medidores']}")
                print(f"   Medidores activos: {estado['medidores_activos']}")
                print(f"   Muestras: {estado['total_muestras']}")
                print(f"   Potencia total: {estado['potencia_total_kW']} kW")
                print(f"   Energia consumida: {estado['energia_consumida_kWh']} kWh")
                print(f"   Energia generada: {estado['energia_generada_kWh']} kWh")
                print(f"   Alertas activas: {estado['alertas_activas']}")
            elif opcion == "3":
                alertas = gestor.obtener_alertas(solo_activas=True)
                if alertas:
                    print(f"\nALERTAS ACTIVAS ({len(alertas)}):")
                    for i, alerta in enumerate(alertas, 1):
                        print(f"   {i}. {alerta['mensaje']}")
                        print(f"      Medidor: {alerta['id_medidor']}")
                        print(f"      Gravedad: {alerta['gravedad']}")
                else:
                    print("\nNo hay alertas activas")
            elif opcion == "4":
                reporte = gestor.generar_reporte()
                print(reporte)
            elif opcion == "5":
                prueba_singleton()
            elif opcion == "6":
                print("\nDeteniendo sistema...")
                for medidor in medidores:
                    medidor.detener()
                print("Sistema detenido")
                sys.exit(0)
            else:
                print("Opcion no valida")
                
    except KeyboardInterrupt:
        print("\n\nDeteniendo sistema...")
        for medidor in medidores:
            medidor.detener()
        print("Sistema detenido")

def prueba_singleton():
    print("\nPRUEBA DEL PATRON SINGLETON")
    print("="*50)
    
    gestor1 = GestorRedInteligente()
    gestor2 = GestorRedInteligente()
    gestor3 = GestorRedInteligente()
    
    print(f"Instancia 1 ID: {id(gestor1)}")
    print(f"Instancia 2 ID: {id(gestor2)}")
    print(f"Instancia 3 ID: {id(gestor3)}")
    
    if id(gestor1) == id(gestor2) == id(gestor3):
        print("\nEXITO: Todas las instancias son la MISMA")
        print("El patron Singleton funciona correctamente")
    else:
        print("\nERROR: Las instancias son diferentes")
        print("El patron Singleton NO funciona")
    
    gestor1.metricas_energeticas['muestras_totales'] = 100
    print(f"\nPrueba de comparticion de datos:")
    print(f"   gestor1.muestras = {gestor1.metricas_energeticas['muestras_totales']}")
    print(f"   gestor2.muestras = {gestor2.metricas_energeticas['muestras_totales']}")
    print(f"   gestor3.muestras = {gestor3.metricas_energeticas['muestras_totales']}")
    
    if (gestor1.metricas_energeticas['muestras_totales'] == 
        gestor2.metricas_energeticas['muestras_totales'] == 
        gestor3.metricas_energeticas['muestras_totales']):
        print("Los datos se comparten correctamente entre todas las instancias")

def main():
    mostrar_banner()
    
    try:
        iniciar_sistema()
    except KeyboardInterrupt:
        print("\n\nSistema detenido")
        sys.exit(0)

if __name__ == "__main__":
    main()