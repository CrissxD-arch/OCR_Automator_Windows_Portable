#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sistema de Debug para OCR Automator - Versión Limpia
Visualiza el procesamiento OCR paso a paso.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import html

debug_logger = logging.getLogger('debug_system')

class DebugSystem:
    """Sistema de debug limpio para OCR Automator."""
    
    def __init__(self, output_dir: str = "debug_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Archivos de debug
        self.debug_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.ocr_debug_file = self.output_dir / f"ocr_debug_{self.debug_session}.json"
        self.processing_debug_file = self.output_dir / f"processing_debug_{self.debug_session}.json"
        self.html_report_file = self.output_dir / f"debug_report_{self.debug_session}.html"
        
        # Datos de debug
        self.ocr_data = {}
        self.processing_data = {}
        self.step_counter = 0
        
        debug_logger.info(f"🔧 Debug iniciado: {self.debug_session}")
    
    def log_ocr_extraction(self, pdf_path: str, page_num: int, raw_text: str, 
                          extracted_data: Dict[str, Any]):
        """Registra la extracción OCR de una página."""
        file_key = Path(pdf_path).name
        
        if file_key not in self.ocr_data:
            self.ocr_data[file_key] = {
                'pdf_path': pdf_path,
                'pages': {},
                'total_extracted_fields': 0,
                'timestamp': datetime.now().isoformat()
            }
        
        clean_text = self._clean_text(raw_text)
        
        self.ocr_data[file_key]['pages'][f'page_{page_num}'] = {
            'raw_text': clean_text,
            'extracted_fields': extracted_data,
            'field_count': len([v for v in extracted_data.values() if v]),
            'patterns': self._find_patterns(raw_text),
            'confidence': self._calculate_confidence(raw_text, extracted_data)
        }
        
        self.ocr_data[file_key]['total_extracted_fields'] += len([v for v in extracted_data.values() if v])
        debug_logger.info(f"📄 {file_key} página {page_num}: {len([v for v in extracted_data.values() if v])} campos")
    
    def log_processing_step(self, step_name: str, input_data: Any, output_data: Any, 
                           metadata: Optional[Dict[str, Any]] = None):
        """Registra un paso del procesamiento."""
        self.step_counter += 1
        step_key = f"step_{self.step_counter:03d}_{step_name}"
        
        self.processing_data[step_key] = {
            'step_name': step_name,
            'step_number': self.step_counter,
            'timestamp': datetime.now().isoformat(),
            'input_type': type(input_data).__name__,
            'output_type': type(output_data).__name__,
            'metadata': metadata or {}
        }
        
        debug_logger.info(f"🔄 Paso {self.step_counter}: {step_name}")
    
    def log_data_transformation(self, field_name: str, original_value: Any, 
                               final_value: Any, transformation_type: str):
        """Registra una transformación de datos."""
        transform_key = f"transform_{len(self.processing_data) + 1}"
        
        self.processing_data[transform_key] = {
            'type': 'transformation',
            'field_name': field_name,
            'original_value': str(original_value) if original_value else None,
            'final_value': str(final_value) if final_value else None,
            'transformation_type': transformation_type,
            'timestamp': datetime.now().isoformat(),
            'changed': original_value != final_value
        }
    
    def create_interactive_debug_report(self):
        """Crea un reporte HTML."""
        html_content = self._generate_html_report()
        
        with open(self.html_report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        debug_logger.info(f"📊 Reporte creado: {self.html_report_file}")
        return str(self.html_report_file)
    
    def save_debug_data(self):
        """Guarda datos de debug en JSON."""
        with open(self.ocr_debug_file, 'w', encoding='utf-8') as f:
            json.dump(self.ocr_data, f, indent=2, ensure_ascii=False)
        
        with open(self.processing_debug_file, 'w', encoding='utf-8') as f:
            json.dump(self.processing_data, f, indent=2, ensure_ascii=False)
        
        debug_logger.info(f"💾 Datos guardados en: {self.output_dir}")
    
    def _clean_text(self, text: str) -> str:
        """Limpia texto para visualización."""
        if not text:
            return ""
        
        # Limpiar caracteres especiales
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)
        
        # Truncar si es muy largo
        if len(text) > 3000:
            text = text[:3000] + "\n... [TRUNCADO] ..."
        
        return text.strip()
    
    def _find_patterns(self, text: str) -> Dict[str, int]:
        """Encuentra patrones importantes en el texto."""
        patterns = {
            'rut': len(re.findall(r'\b\d{7,8}[-.]?[0-9kK]\b', text, re.I)),
            'montos': len(re.findall(r'\$?\s*[\d,.]+', text)),
            'fechas': len(re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text)),
            'operaciones': len(re.findall(r'\b\d{10,15}\b', text))
        }
        
        return {k: v for k, v in patterns.items() if v > 0}
    
    def _calculate_confidence(self, raw_text: str, extracted_data: Dict[str, Any]) -> float:
        """Calcula la confianza de la extracción."""
        if not raw_text:
            return 0.0
        
        # Evaluar calidad del texto
        readable_chars = len(re.findall(r'[a-zA-Z0-9áéíóúñÁÉÍÓÚÑ\s]', raw_text))
        total_chars = len(raw_text)
        text_quality = readable_chars / total_chars if total_chars > 0 else 0.0
        
        # Evaluar completitud de extracción
        fields_filled = len([v for v in extracted_data.values() if v])
        total_fields = len(extracted_data)
        extraction_rate = fields_filled / total_fields if total_fields > 0 else 0.0
        
        # Combinar métricas
        return (text_quality * 0.6 + extraction_rate * 0.4)
    def _generate_html_report(self) -> str:
        """Genera reporte HTML simple."""
        ocr_content = self._generate_ocr_html()
        processing_content = self._generate_processing_html()
        
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Debug OCR Automator</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        .header {{ background: #2c3e50; color: white; padding: 15px; margin: -20px -20px 20px -20px; }}
        .pdf-section {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; }}
        .pdf-title {{ background: #34495e; color: white; padding: 10px; margin: -15px -15px 10px -15px; }}
        .text-box {{ background: #f8f9fa; padding: 10px; margin: 10px 0; max-height: 200px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; }}
        .fields {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
        .field {{ background: #e8f5e8; padding: 8px; border-left: 3px solid #28a745; }}
        .field.empty {{ background: #fff3cd; border-left-color: #ffc107; }}
        .confidence {{ background: #e9ecef; height: 15px; border-radius: 8px; margin: 5px 0; }}
        .confidence-fill {{ height: 100%; background: #28a745; border-radius: 8px; }}
        .step {{ background: #f8f9fa; margin: 10px 0; padding: 10px; border-left: 3px solid #6c757d; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔧 Debug OCR Automator</h1>
            <p>Sesión: {self.debug_session}</p>
        </div>
        
        <h2>📄 Datos OCR</h2>
        {ocr_content}
        
        <h2>⚙️ Procesamiento</h2>
        {processing_content}
    </div>
</body>
</html>"""
    
    def _generate_ocr_html(self) -> str:
        """Genera HTML para datos OCR."""
        if not self.ocr_data:
            return "<p>No hay datos OCR disponibles.</p>"
        
        html_parts = []
        
        for pdf_name, pdf_data in self.ocr_data.items():
            html_parts.append(f"""
            <div class="pdf-section">
                <div class="pdf-title">📄 {pdf_name} ({len(pdf_data['pages'])} páginas)</div>
            """)
            
            for page_name, page_data in pdf_data['pages'].items():
                confidence = page_data['confidence']
                confidence_percent = int(confidence * 100)
                
                # Campos extraídos
                fields_html = []
                for field_name, field_value in page_data['extracted_fields'].items():
                    field_class = "field" if field_value else "field empty"
                    display_value = field_value if field_value else "(vacío)"
                    fields_html.append(f"""
                    <div class="{field_class}">
                        <strong>{field_name}:</strong> {html.escape(str(display_value))}
                    </div>
                    """)
                
                html_parts.append(f"""
                <h4>📖 {page_name.replace('_', ' ').title()}</h4>
                
                <div>
                    <strong>Confianza:</strong>
                    <div class="confidence">
                        <div class="confidence-fill" style="width: {confidence_percent}%"></div>
                    </div>
                    {confidence_percent}% | Campos: {page_data['field_count']}
                </div>
                
                <strong>Texto OCR:</strong>
                <div class="text-box">{html.escape(page_data['raw_text'][:1500])}{'...' if len(page_data['raw_text']) > 1500 else ''}</div>
                
                <strong>Campos extraídos:</strong>
                <div class="fields">
                    {''.join(fields_html)}
                </div>
                """)
            
            html_parts.append("</div>")
        
        return ''.join(html_parts)
    
    def _generate_processing_html(self) -> str:
        """Genera HTML para datos de procesamiento."""
        if not self.processing_data:
            return "<p>No hay datos de procesamiento disponibles.</p>"
        
        html_parts = []
        
        for step_key, step_data in self.processing_data.items():
            if step_data.get('type') == 'transformation':
                html_parts.append(f"""
                <div class="step">
                    <strong>🔄 {step_data['field_name']}</strong> ({step_data['transformation_type']})
                    <br>Original: <code>{step_data['original_value'] or 'N/A'}</code>
                    <br>Final: <code>{step_data['final_value'] or 'N/A'}</code>
                    <br>Estado: {'✓ Transformado' if step_data['changed'] else '⚠ Sin cambios'}
                </div>
                """)
            else:
                html_parts.append(f"""
                <div class="step">
                    <strong>⚙️ Paso {step_data['step_number']}: {step_data['step_name']}</strong>
                    <br>Entrada: {step_data['input_type']} → Salida: {step_data['output_type']}
                </div>
                """)
        
        return ''.join(html_parts)


def initialize_debug_system(enable_debug: bool = True) -> Optional[DebugSystem]:
    """Inicializa el sistema de debug."""
    if not enable_debug:
        return None
    
    debug_system = DebugSystem()
    debug_logger.info("🔧 Sistema de debug inicializado")
    return debug_system


def finalize_debug_system(debug_system: Optional[DebugSystem]) -> Optional[str]:
    """Finaliza el sistema de debug y genera reportes."""
    if not debug_system:
        return None
    
    debug_system.save_debug_data()
    report_path = debug_system.create_interactive_debug_report()
    debug_logger.info(f"📊 Debug completado. Reporte: {report_path}")
    return report_path