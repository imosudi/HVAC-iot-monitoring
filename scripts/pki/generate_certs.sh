#!/usr/bin/env bash
# ==============================================================================
# Public Key Infrastructure (PKI) Certificate Generation Script
# Automotive IoT HVAC Monitoring - FHTW-AIOT Research Cluster
#
# Generates private Root CA, broker server certificate, and client certificates
# for mutual TLS 1.3 authentication across the automotive edge service mesh.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}/../../deploy/mosquitto/certs"

mkdir -p "${CERTS_DIR}"
cd "${CERTS_DIR}"

echo "[INFO] Initialising private Root CA..."
openssl ecparam -name prime256v1 -genkey -noout -out ca.key
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
    -subj "/C=AT/ST=Vienna/L=Vienna/O=FH Technikum Wien/OU=FHTW-AIOT/CN=FHTW-Automotive-RootCA"

echo "[INFO] Generating broker server keypair and certificate..."
openssl ecparam -name prime256v1 -genkey -noout -out server.key
openssl req -new -key server.key -out server.csr \
    -subj "/C=AT/ST=Vienna/L=Vienna/O=FH Technikum Wien/OU=MEC-Gateway/CN=mosquitto.sdv.local"

cat > server_ext.cnf <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = mosquitto.sdv.local
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days 730 -extfile server_ext.cnf

echo "[INFO] Generating ESP32-S3 cabin node client certificate..."
openssl ecparam -name prime256v1 -genkey -noout -out client_esp32.key
openssl req -new -key client_esp32.key -out client_esp32.csr \
    -subj "/C=AT/ST=Vienna/L=Vienna/O=FH Technikum Wien/OU=VehicularNodes/CN=vehicle_edge_node_01"

openssl x509 -req -in client_esp32.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out client_esp32.crt -days 730

echo "[INFO] Generating Node-RED Ingress IPE client certificate..."
openssl ecparam -name prime256v1 -genkey -noout -out client_nodered.key
openssl req -new -key client_nodered.key -out client_nodered.csr \
    -subj "/C=AT/ST=Vienna/L=Vienna/O=FH Technikum Wien/OU=MEC-IPE/CN=nodered_ipe_gateway"

openssl x509 -req -in client_nodered.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out client_nodered.crt -days 730

# Clean up CSRs and temporary files
rm -f *.csr server_ext.cnf

# Secure file permissions
chmod 600 *.key
chmod 644 *.crt

echo "[SUCCESS] PKI certificate generation complete in ${CERTS_DIR}"
