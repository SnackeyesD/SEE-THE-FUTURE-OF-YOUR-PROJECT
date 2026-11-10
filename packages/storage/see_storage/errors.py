class StorageError(Exception):
    """Erreur de persistance locale."""


class StorageValidationError(StorageError):
    """Paramètre invalide pour une opération de stockage."""


class ProjectNotFound(StorageError):
    """Projet inexistant ou supprimé."""


class IntegrityError(StorageError):
    """Base locale corrompue ou sauvegarde invalide."""


class SchemaTooNewError(StorageError):
    """Base créée par une version plus récente de l'application."""


class PortableError(StorageError):
    """Archive .simproj invalide ou incohérente."""
