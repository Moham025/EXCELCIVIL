# Utiliser une image Python officielle
<<<<<<< HEAD
FROM docker.io/library/python:3.11-slim
=======
FROM python:3.9-slim
>>>>>>> de0960da42692f91b54fcd7d0f4f006613c494ce

# Définir le répertoire de travail dans le conteneur
WORKDIR /code

<<<<<<< HEAD
# Variables d'environnement pour tous les caches (à définir AVANT l'installation)
ENV TRANSFORMERS_CACHE=/tmp/transformers_cache
ENV HF_HOME=/tmp/huggingface_cache
ENV SENTENCE_TRANSFORMERS_HOME=/tmp/sentence_transformers_cache
ENV TORCH_HOME=/tmp/torch_cache
ENV HUGGINGFACE_HUB_CACHE=/tmp/huggingface_hub_cache
ENV HF_DATASETS_CACHE=/tmp/datasets_cache

# Créer tous les répertoires de cache nécessaires avec permissions appropriées
RUN mkdir -p /tmp/app_cache \
    /tmp/transformers_cache \
    /tmp/huggingface_cache \
    /tmp/sentence_transformers_cache \
    /tmp/torch_cache \
    /tmp/huggingface_hub_cache \
    /tmp/datasets_cache && \
    chmod -R 777 /tmp/

# Créer un utilisateur non-root pour plus de sécurité
RUN useradd --create-home --shell /bin/bash app_user && \
    chown -R app_user:app_user /code

=======
>>>>>>> de0960da42692f91b54fcd7d0f4f006613c494ce
# Copier le fichier des dépendances et les installer
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copier tout le reste de votre code
COPY . /code/

<<<<<<< HEAD
# Changer vers l'utilisateur non-root
USER app_user

=======
>>>>>>> de0960da42692f91b54fcd7d0f4f006613c494ce
# Indiquer que l'application écoutera sur le port 7860 (port par défaut de HF Spaces)
EXPOSE 7860

# La commande pour démarrer votre application avec Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "app:app"]