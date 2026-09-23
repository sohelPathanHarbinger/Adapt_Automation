"""Word-side of the pipeline: .docx in, :mod:`adapt_builder.model` tree out."""

from .parser import parse_storyboard

__all__ = ["parse_storyboard"]
