"""Configuração comum dos testes."""

import matplotlib

# Os testes só salvam figuras em arquivo. Forçar o "Agg" evita depender do Tcl/Tk do
# Python instalado: no Windows, um Tcl/Tk quebrado gerava "Can't find a usable init.tcl"
# e travava o pytest (0x80000003) durante o garbage collection nos testes do Streamlit.
matplotlib.use("Agg", force=True)
