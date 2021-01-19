#FROM python:3.7-slim
FROM jjanzic/docker-python3-opencv

ENV PYTHONIOENCODING=utf-8
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/service_account.json
ENV BUCKET_NAME=shipt-test-images
ENV CONFIG=production
ENV SECRET_KEY=secretkey
ENV EXPORT_PASSWORD=exportpassword
ENV TWILIO_SID=sid
ENV TWILIO_TOKEN=accounttoken
ENV TWILIO_NUMBER="+5555555555"

COPY . /app
WORKDIR /app
RUN mkdir -p /root/.config/gspread
RUN mkdir -p /home/.config/gspread
COPY service_account.json /home/.config/gspread
COPY service_account.json /root/.config/gspread
RUN apt update && apt install -y libsm6 libxext6
RUN apt-get -y install tesseract-ocr
RUN pip install -r requirements.txt 
EXPOSE 8080 
ENTRYPOINT [ "waitress-serve" ] 
CMD [ "--call", "shipt:create_app" ] 
