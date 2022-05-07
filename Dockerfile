FROM python
label org.opencontainers.image.source = "https://github.com/Tweeticoats/stash-vr-companion"
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV CACHE_DIR /cache/
COPY requirements.txt /
RUN pip3 install -r /requirements.txt

COPY . /app
WORKDIR /app

#CMD [ "flask","run","--host=0.0.0.0"]
CMD ["uwsgi","--http=:5000","--wsgi-file=app.py","--callable", "app","--enable-threads"]
