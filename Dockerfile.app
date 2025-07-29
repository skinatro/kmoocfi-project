FROM python:3-slim

WORKDIR /usr/src/app

COPY ./src .

RUN pip install -r requirements.txt

CMD ["python","-u","./todo-app.py"]