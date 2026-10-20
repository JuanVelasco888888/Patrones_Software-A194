from core.smart_grid_facade import SmartGridFacade
from core.grid_builder import GridBuilder

# Crear configuración
config = (GridBuilder()
    .add_source('solar', 'Panel Test', 40)
    .set_peak_threshold(70)
    .build())

# Probar con rol 'invitado' (debe fallar al registrar fuentes)
print("--- Probando rol: invitado ---")
facade = SmartGridFacade(user_role='invitado')
try:
    billing, monitor = facade.run_simulation_cycle(config, verbose=False)
    print('ERROR: No debería permitir registrar fuentes')
except PermissionError as e:
    print(f'OK: Proxy bloqueó la operación -> {e}')

# Probar con rol 'operator' (puede registrar pero no resetear)
print("\n--- Probando rol: operator ---")
facade_op = SmartGridFacade(user_role='operator')
try:
    facade_op.monitor.reset()
    print('ERROR: operator no debería poder resetear')
except PermissionError as e:
    print(f'OK: Proxy bloqueó el reset -> {e}')

# Probar con rol 'admin' (debe funcionar todo)
print("\n--- Probando rol: admin ---")
facade_admin = SmartGridFacade(user_role='admin')
billing, monitor = facade_admin.run_simulation_cycle(config, verbose=False)
print(f'OK: Admin ejecutó la simulación. Costo total: ${billing.total_cost():.2f}')
print(f'OK: Alertas generadas: {len(monitor.get_alerts())}')