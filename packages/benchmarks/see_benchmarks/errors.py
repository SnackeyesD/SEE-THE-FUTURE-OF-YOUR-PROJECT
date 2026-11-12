from __future__ import annotations


class BenchmarkError(Exception):
    """Erreur de base du référentiel local."""


class PackValidationError(BenchmarkError):
    """Pack invalide ou non conforme au schéma."""


class SignatureError(BenchmarkError):
    """Signature absente, invalide ou clé inconnue."""


class SignatureMissingError(SignatureError):
    """Aucun fichier de signature détachée n'est présent."""


class UnknownKeyError(SignatureError):
    """La clé de signature n'est pas dans le jeu de clés publiques."""


class KeyRetiredError(SignatureError):
    """La clé de signature a été retirée."""


class InvalidSignatureError(SignatureError):
    """La signature ne correspond pas au contenu exact du pack."""


class ImportPackError(BenchmarkError):
    """Import de pack refusé."""
