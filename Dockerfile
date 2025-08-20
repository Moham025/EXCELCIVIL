# Utiliser une image Python officielle
FROM python:3.9-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /code

# Copier le fichier des dépendances et les installer
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copier tout le reste de votre code
COPY . /code/

# Indiquer que l'application écoutera sur le port 7860 (port par défaut de HF Spaces)
EXPOSE 7860

# La commande pour démarrer votre application avec Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "app:app"]