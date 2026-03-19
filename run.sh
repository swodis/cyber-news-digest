#!/bin/bash
# Portable runner for cyber-news-digest
# Works on any machine with Node.js and Ollama
cd "$(dirname "$0")"
exec node index.js
