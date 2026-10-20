from main import default_configuration

config = default_configuration()

print("Configuracion construida con GridBuilder:")
print(config)
print()
print("Fuentes especificadas:")
for tipo, nombre, cap in config.sources_spec:
    print(f"  - {tipo:15s} | {nombre:22s} | {cap} kW")