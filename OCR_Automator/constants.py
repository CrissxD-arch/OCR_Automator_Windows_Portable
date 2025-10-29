#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Constantes para el procesamiento de datos Itaú.

Este archivo contiene todas las configuraciones y patrones necesarios
para procesar correctamente los archivos CSV extraídos de los PDFs de Itaú.
"""

import re
from typing import Dict, List, Set

# ========================= HEADERS Y ALIASES =========================

# Headers canónicos basados en el Excel base de Itaú (estructura exacta)
CANONICAL_HEADERS = [
    'OPERACION_1',
    'RUT',
    'DV',
    'NOMBRE',
    'DIRECCION',
    'COMUNA',
    'FECHA_SUSCRIPCION_1',
    'MONTO_CREDITO_1',
    'CUOTAS_1',
    'TASA_1',
    'MONTO_CUOTA_1',
    'MONTO_ULTIMA_CUOTA_1',
    'FECHA_VENCIMIENTO_1ª_CUOTA_1',
    'FECHA_VENCIMIENTO_ULTIMA_CUOTA_1',
    'CUOTA_MOROSA_1',
    'FECHA_CUOTA_MOROSA_1',
    'CAPITAL_1',
    'EXHORTO',
    'SUCURSAL',
    'PRODUCTO',
    'NOMBRE_APODERADO',
    'NOMBRE_APODERADO_2'
]

# Aliases comunes para headers (mapeo de variaciones → canónico según Excel base)
HEADER_ALIASES = {
    # Operación
    'operacion': 'OPERACION_1',
    'numero_operacion': 'OPERACION_1',
    'num_operacion': 'OPERACION_1',
    'op': 'OPERACION_1',
    
    # RUT Cliente
    'rut_cliente': 'RUT',
    'rutcliente': 'RUT',
    'rut cliente': 'RUT',
    'cedula': 'RUT',
    
    # Dígito Verificador
    'digito_verificador': 'DV',
    'dv': 'DV',
    
    # Nombre
    'nombre_completo': 'NOMBRE',
    'nombre completo': 'NOMBRE',
    'nombres': 'NOMBRE',
    'apellidos': 'NOMBRE',
    'razón social': 'NOMBRE',
    'razon social': 'NOMBRE',
    'deudor': 'NOMBRE',
    'cliente': 'NOMBRE',
    
    # Dirección
    'direccion': 'DIRECCION',
    'dirección': 'DIRECCION',
    'domicilio': 'DIRECCION',
    'domicilio particular': 'DIRECCION',
    
    # Comuna
    'ciudad': 'COMUNA',
    'localidad': 'COMUNA',
    
    # Fecha Suscripción
    'fecha_suscripcion': 'FECHA_SUSCRIPCION_1',
    'fecha suscripcion': 'FECHA_SUSCRIPCION_1',
    'fecha_contrato': 'FECHA_SUSCRIPCION_1',
    'fecha contrato': 'FECHA_SUSCRIPCION_1',
    'fecha_firma': 'FECHA_SUSCRIPCION_1',
    'fecha firma': 'FECHA_SUSCRIPCION_1',
    
    # Monto Crédito
    'monto': 'MONTO_CREDITO_1',
    'monto_credito': 'MONTO_CREDITO_1',
    'monto credito': 'MONTO_CREDITO_1',
    'monto crédito': 'MONTO_CREDITO_1',
    'valor credito': 'MONTO_CREDITO_1',
    'importe': 'MONTO_CREDITO_1',
    'cantidad': 'MONTO_CREDITO_1',
    
    # Cuotas
    'cuotas': 'CUOTAS_1',
    'numero cuotas': 'CUOTAS_1',
    'num_cuotas': 'CUOTAS_1',
    'plazo': 'CUOTAS_1',
    'plazo_meses': 'CUOTAS_1',
    'plazo meses': 'CUOTAS_1',
    
    # Tasa
    'tasa': 'TASA_1',
    'tasa_interes': 'TASA_1', 
    'tasa interes': 'TASA_1',
    'tasa interés': 'TASA_1',
    'tasa anual': 'TASA_1',
    'interes': 'TASA_1',
    'interés': 'TASA_1',
    
    # Monto Cuota
    'monto_cuota': 'MONTO_CUOTA_1',
    'cuota_mensual': 'MONTO_CUOTA_1',
    'valor_cuota': 'MONTO_CUOTA_1',
    'iguales': 'MONTO_CUOTA_1',
    'mpc': 'MONTO_CUOTA_1',
    
    # Monto Última Cuota
    'monto_ultima_cuota': 'MONTO_ULTIMA_CUOTA_1',
    'ultima_cuota': 'MONTO_ULTIMA_CUOTA_1',
    'muc': 'MONTO_ULTIMA_CUOTA_1',
    
    # Fechas de vencimiento
    'fecha_primera_cuota': 'FECHA_VENCIMIENTO_1_CUOTA_1',
    'fecha_vencimiento_primera': 'FECHA_VENCIMIENTO_1_CUOTA_1',
    'fpv': 'FECHA_VENCIMIENTO_1_CUOTA_1',
    'fecha_ultima_cuota': 'FECHA_VENCIMIENTO_ULTIMA_CUOTA_1',
    'fecha_vencimiento_ultima': 'FECHA_VENCIMIENTO_ULTIMA_CUOTA_1',
    'fuv': 'FECHA_VENCIMIENTO_ULTIMA_CUOTA_1',
    
    # Capital
    'capital': 'CAPITAL_1',
    'capital_insoluto': 'CAPITAL_1',
    'saldo_capital': 'CAPITAL_1',
    
    # Exhorto
    'exhorto': 'EXHORTO',
    'tribunal': 'EXHORTO',
    'juzgado': 'EXHORTO',
    
    # Sucursal
    'oficina': 'SUCURSAL',
    'agencia': 'SUCURSAL',
    
    # Producto
    'codigo_producto': 'PRODUCTO',
    'código producto': 'PRODUCTO',
    'tipo_credito': 'PRODUCTO',
    'tipo_producto': 'PRODUCTO',
    
    # Apoderados
    'apoderado_1': 'NOMBRE_APODERADO',
    'apoderado 1': 'NOMBRE_APODERADO',
    'nombre_apoderado_1': 'NOMBRE_APODERADO',
    'apoderado_2': 'NOMBRE_APODERADO_2',
    'apoderado 2': 'NOMBRE_APODERADO_2'
}

# ========================= CAMPOS DE TIPOS DE DATOS =========================

# Campos que deben ser tratados como fechas
DATE_FIELDS = {
    'FECHA_SUSCRIPCION_1',
    'FECHA_VENCIMIENTO_1_CUOTA_1',
    'FECHA_VENCIMIENTO_ULTIMA_CUOTA_1',
    'FECHA_CUOTA_MOROSA_1'
}

# Campos que deben ser tratados como enteros
INT_FIELDS = {
    'CUOTAS_1',
    'CUOTA_MOROSA_1'
}

# Campos monetarios (que requieren formato especial)
MONEY_FIELDS = {
    'MONTO_CREDITO_1',
    'MONTO_CUOTA_1', 
    'MONTO_ULTIMA_CUOTA_1',
    'CAPITAL_1'
}

# Campos de tasa (porcentajes)
RATE_FIELDS = {
    'TASA_1'
}

# ========================= PATRONES DE APODERADOS =========================

# RUTs de apoderados conocidos (formato sin puntos ni guión)
APODERADO_1 = {
    '12345678': 'Juan Pérez Apoderado',
    '87654321': 'María González Representante',
    '11111111': 'Pedro Rodríguez Autorizado',
    # Agregar más RUTs conocidos aquí
}

APODERADO_2 = {
    '22222222': 'Ana Martínez Suplente',
    '33333333': 'Carlos López Adjunto',
    # Agregar más RUTs conocidos aquí
}

# Patrones regex para detectar apoderados en texto libre
APODERADO_PATTERN_STRS = [
    r'apoderado\s*[:\-]?\s*([^,\n]+)',
    r'representante\s*[:\-]?\s*([^,\n]+)',
    r'autorizado\s*[:\-]?\s*([^,\n]+)',
    r'poder\s*[:\-]?\s*([^,\n]+)',
    r'en\s*representaci[óo]n\s*de\s*([^,\n]+)',
]

# ========================= CORRECCIONES COMUNES =========================

# Diccionario de correcciones comunes de texto
COMMON_FIXES = {
    # Caracteres mal codificados
    'Ãº': 'ú',
    'Ã±': 'ñ', 
    'Ã¡': 'á',
    'Ã©': 'é',
    'Ã­': 'í',
    'Ãó': 'ó',
    'Ã¼': 'ü',
    'Ã': 'Á',
    'Ã‰': 'É',
    'Ã­': 'Í',
    'Ã"': 'Ó',
    'Ãš': 'Ú',
    'Ã\u00d1': 'Ñ',
    
    # Espaciado
    '  ': ' ',
    '\t': ' ',
    '\r': '',
    '\n': ' ',
    
    # Caracteres especiales problemáticos
    '"': '"',
    '"': '"',
    ''': "'",
    ''': "'",
    '–': '-',
    '—': '-',
    '…': '...',
    
    # Abreviaciones comunes
    'S.A.': 'SA',
    'LTDA.': 'LTDA',
    'E.I.R.L.': 'EIRL',
    'SPA.': 'SPA',
}

# ========================= COMUNAS VÁLIDAS =========================

# Set de comunas válidas en Chile (muestra)
VALID_COMUNAS: Set[str] = {
    'SANTIAGO',
    'LAS CONDES', 
    'PROVIDENCIA',
    'ÑUÑOA',
    'LA REINA',
    'VITACURA',
    'LO BARNECHEA',
    'MAIPÚ',
    'PUENTE ALTO',
    'SAN MIGUEL',
    'LA FLORIDA',
    'PEÑALOLÉN',
    'MACUL',
    'SAN JOAQUÍN',
    'PEDRO AGUIRRE CERDA',
    'SAN RAMÓN',
    'LA CISTERNA',
    'EL BOSQUE',
    'LA PINTANA',
    'SAN BERNARDO',
    'CALERA DE TANGO',
    'PIRQUE',
    'PUENTE ALTO',
    'QUILICURA',
    'HUECHURABA',
    'RECOLETA',
    'INDEPENDENCIA',
    'CONCHALÍ',
    'RENCA',
    'CERRO NAVIA',
    'QUINTA NORMAL',
    'LO PRADO',
    'ESTACIÓN CENTRAL',
    'CERRILLOS',
    'MAIPÚ',
    'PUDAHUEL',
    'PADRE HURTADO',
    'MELIPILLA',
    'TALAGANTE',
    'PEÑAFLOR',
    'EL MONTE',
    'ISLA DE MAIPO',
    'CURACAVÍ',
    'MARÍA PINTO',
    'SAN PEDRO',
    'ALHUÉ',
    'VALPARAÍSO',
    'VIÑA DEL MAR',
    'CONCÓN',
    'QUILPUÉ',
    'VILLA ALEMANA',
    'LIMACHE',
    'OLMUÉ',
    'QUILLOTA',
    'LA CALERA',
    'HIJUELAS',
    'LA CRUZ',
    'NOGALES',
    'SAN ANTONIO',
    'CARTAGENA',
    'EL TABO',
    'EL QUISCO',
    'ALGARROBO',
    'SANTO DOMINGO',
    'RANCAGUA',
    'MACHALÍ',
    'GRANEROS',
    'CODEGUA',
    'REQUÍNOA',
    'RENGO',
    'OLIVAR',
    'DOÑIHUE',
    'COLTAUCO',
    'COINCO',
    'PEUMO',
    'PICHIDEGUA',
    'SAN VICENTE',
    'NAVIDAD',
    'LITUECHE',
    'LA ESTRELLA',
    'MARCHIHUE',
    'PAREDONES',
    'PICHILEMU',
    # Agregar más comunas según necesidades
}

# ========================= CONFIGURACIÓN DE VALIDACIÓN =========================

# Campos obligatorios (si se usa validación estricta)
REQUIRED_FIELDS = {
    'RUT_CLIENTE',
    'NOMBRE_COMPLETO',
    'MONTO_CREDITO'
}

# Patrones de validación
VALIDATION_PATTERNS = {
    'RUT_CLIENTE': re.compile(r'^\d{7,8}-[\dkK]$'),  # Formato: 12345678-9
    'EMAIL': re.compile(r'^[^@]+@[^@]+\.[^@]+$'),     # Email básico
    'TELEFONO': re.compile(r'^[\d\+\-\s\(\)]{7,15}$'), # Teléfono flexible
}

# ========================= CONFIGURACIÓN DE EXPORTACIÓN =========================

# Configuración para el archivo Excel final
EXCEL_CONFIG = {
    'sheet_name': 'Datos_Itau',
    'freeze_panes': (1, 1),  # Congelar primera fila y columna
    'auto_filter': True,
    'column_widths': {
        'RUT_CLIENTE': 15,
        'NOMBRE_COMPLETO': 30,
        'TELEFONO': 15,
        'EMAIL': 25,
        'DIRECCION': 35,
        'COMUNA': 20,
        'FECHA_NACIMIENTO': 18,
        'PROFESION': 25,
        'MONTO_CREDITO': 15,
        'PLAZO_MESES': 12,
        'TASA_INTERES': 12,
        'FECHA_CONTRATO': 18,
        'RUT_APODERADO_1': 15,
        'NOMBRE_APODERADO_1': 25,
        'RUT_APODERADO_2': 15,
        'NOMBRE_APODERADO_2': 25,
        'SUCURSAL': 20,
        'PRODUCTO': 15,
        'NOMBRE_APODERADO': 25,
        'NOMBRE_APODERADO_2': 25,
        'DIRECCION_NORMALIZADA': 40,
        'COMUNA_VERIFICADA': 20,
        'REGION': 25,
        'LATITUD': 12,
        'LONGITUD': 12,
        'GEOCODING_CONFIDENCE': 15,
        'GEOCODING_SOURCE': 15
    }
}

# Estilos para el Excel
EXCEL_STYLES = {
    'header': {
        'font': {'bold': True, 'color': 'FFFFFF'},
        'fill': {'fill_type': 'solid', 'start_color': '366092'},
        'alignment': {'horizontal': 'center'},
        'border': {'style': 'thin'}
    },
    'currency': {
        'number_format': '$#,##0',
        'alignment': {'horizontal': 'right'}
    },
    'percentage': {
        'number_format': '0.00%',
        'alignment': {'horizontal': 'right'}
    },
    'date': {
        'number_format': 'DD/MM/YYYY',
        'alignment': {'horizontal': 'center'}
    }
}