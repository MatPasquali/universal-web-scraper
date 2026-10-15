# -*- coding: utf-8 -*-
"""Põe a raiz do projeto no sys.path para os testes importarem os módulos soltos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
