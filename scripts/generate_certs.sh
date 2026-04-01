#!/bin/bash
# ============================================================
# Generate self-signed TLS certificate for local development
#
# For production: use Let's Encrypt (certbot) with a real domain
# This script is for local dev only.
# ============================================================

CERT_DIR="$(dirname "$0")/../nginx/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERT_DIR/medisense.key" \
    -out "$CERT_DIR/medisense.crt" \
    -subj "/C=MA/ST=Marrakesh/L=Marrakesh/O=MediSense AI/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "✓ Self-signed certificate generated at $CERT_DIR"
echo "  Valid for 365 days (development only)"
echo ""
echo "  To trust it in your browser:"
echo "  macOS: sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $CERT_DIR/medisense.crt"
