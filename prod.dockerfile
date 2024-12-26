# Usa uma imagem base leve do Python
FROM python:3.12-slim

# Instala dependências do sistema necessárias para compilar pacotes Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gcc libffi-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Copia os arquivos do projeto para o container
COPY . /code
WORKDIR /code

# Configura o Poetry para o ambiente de produção e instala as dependências
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-root --only main

# Expõe a porta do container (ajuste conforme necessário)
EXPOSE 8000

# Define variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    ENV_FILE_PATH=../.env.prod

# Comando para iniciar a aplicação com Uvicorn
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]