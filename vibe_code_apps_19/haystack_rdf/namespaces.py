"""Haystack + Open-FDD extension namespaces for TTL/SPARQL."""

from __future__ import annotations

PH = "https://project-haystack.org/def/"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
OFDD = "http://openfdd.local/ontology#"
SITE = "http://openfdd.local/site#"

PREFIXES_TTL = f"""@prefix ph: <{PH}> .
@prefix rdfs: <{RDFS}> .
@prefix rdf: <{RDF}> .
@prefix ofdd: <{OFDD}> .
@prefix : <{SITE}> .
"""

PREFIXES_SPARQL = f"""PREFIX ph: <{PH}>
PREFIX rdfs: <{RDFS}>
PREFIX rdf: <{RDF}>
PREFIX ofdd: <{OFDD}>
PREFIX : <{SITE}>
"""
