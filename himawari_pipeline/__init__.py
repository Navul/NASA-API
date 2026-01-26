"""
Himawari-8 Satellite Data Pipeline

A modular, efficient pipeline for downloading, preprocessing, and storing
Himawari-8 satellite imagery over Bangladesh for lightning nowcasting applications.

Modules:
- config: Configuration management
- downloader: Data acquisition from multiple sources
- preprocessor: Spatial cropping and regridding
- temporal_alignment: 30-minute interval alignment
- storage: Efficient tensor storage
- utils: Validation, visualization, and utilities

Quick Start:
    from himawari_pipeline import HimawariPipeline
    
    pipeline = HimawariPipeline(use_simulated=True)  # For testing
    pipeline.run(start_date='2023-01-01', end_date='2023-01-07')

Author: Himawari Pipeline Team
License: MIT
"""

from .config import PipelineConfig, DEFAULT_CONFIG
from .downloader import HimawariDownloader
from .preprocessor import HimawariPreprocessor
from .temporal_alignment import TemporalAlignmentManager
from .storage import StorageManager, HimawariDataLoader
from .run_pipeline import HimawariPipeline

__version__ = '1.0.0'
__author__ = 'Himawari Pipeline Team'

__all__ = [
    'PipelineConfig',
    'DEFAULT_CONFIG',
    'HimawariDownloader',
    'HimawariPreprocessor',
    'TemporalAlignmentManager',
    'StorageManager',
    'HimawariDataLoader',
    'HimawariPipeline',
]

