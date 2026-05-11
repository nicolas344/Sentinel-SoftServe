"""
Memoria de los agentes — dos subsistemas sobre ChromaDB:

  runbooks.py   → conocimiento curado (humano escribe, agente lee)
  incidents.py  → memoria episódica (agente escribe al cerrar, lee cuando
                  llega un caso similar)

Cada dominio tiene sus propias colecciones:
  runbooks-docker,      incidents-docker
  runbooks-kubernetes,  incidents-kubernetes
    (pendiente — ver docs/kubernetes_integration_handoff.md)
  runbooks-postgres,    incidents-postgres    (activo desde Sprint 2)
"""
