"""Gera um par de chaves VAPID para Web Push.

Rode dentro do container do backend (onde as deps de criptografia existem):

    docker compose exec backend python -m backend.generate_vapid

A saída já vem pronta para colar no docker-compose.yml / ambiente:

    VAPID_PUBLIC_KEY=...
    VAPID_PRIVATE_KEY=...
    VAPID_SUBJECT=mailto:seu-email@exemplo.com

Notas:
  - A chave pública (VAPID_PUBLIC_KEY) é a que vai para o navegador.
  - A chave privada (VAPID_PRIVATE_KEY, formato PEM) fica SOMENTE no servidor.
  - Se você regerar as chaves, todas as inscrições existentes passam a ser
    inválidas e os usuários precisam reativar as notificações.
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def generate() -> tuple[str, str, str]:
    """Gera o par VAPID.

    Retorna (priv_der_b64url, priv_pem, pub_b64url):
      - priv_der_b64url: base64url do DER PKCS#8 — FORMATO QUE O py_vapid/pywebpush
        espera (uma linha, sem cabeçalhos). É o que vai para VAPID_PRIVATE_KEY.
      - priv_pem: PEM multilinha (referência humana).
      - pub_b64url: base64url do ponto público descomprimido — vai para o navegador.
    """
    private_key = ec.generate_private_key(ec.SECP256R1())

    priv_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    priv_der_b64url = base64.urlsafe_b64encode(priv_der).rstrip(b"=").decode("ascii")

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    pub_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    pub_b64url = base64.urlsafe_b64encode(pub_raw).rstrip(b"=").decode("ascii")
    return priv_der_b64url, priv_pem, pub_b64url


def main() -> None:
    priv_der_b64url, priv_pem, pub_b64url = generate()

    print("=" * 70)
    print("CHAVES VAPID GERADAS — Web Push")
    print("=" * 70)
    print()
    print("# >>> COLE ISTO no seu arquivo .env (raiz do projeto): <<<")
    print(f"VAPID_PUBLIC_KEY={pub_b64url}")
    print(f"VAPID_PRIVATE_KEY={priv_der_b64url}")
    print("VAPID_SUBJECT=mailto:contato@seu-dominio.com")
    print()
    print("# (Referência) VAPID_PRIVATE_KEY em PEM multilinha — equivalente:")
    for line in priv_pem.strip().splitlines():
        print(f"#   {line}")
    print()
    print("Lembre-se de NÃO commitar a chave privada (o .env já está no .gitignore).")


if __name__ == "__main__":
    main()
