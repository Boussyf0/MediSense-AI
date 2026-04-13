"""
MCP (Model Context Protocol) servers for live medical data.

MediSense uses MCP to fetch real-time data from authoritative sources,
enriching the static RAG corpus with live drug alerts and disease codes.

Servers:
    ansm_server     French drug database (ANSM / medicaments.gouv.fr)
    icd11_server    WHO ICD-11 disease classification API
    client          Async MCP client with circuit breaker
"""
