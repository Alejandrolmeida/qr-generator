FROM cdrx/pyinstaller-windows

COPY . /src
WORKDIR /src

RUN python -m pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pyinstaller --onefile --add-data ".env;." --add-data "templates/visitor_template_05.pdf;templates" --add-data "fonts/DejaVuSans-Bold.ttf;fonts" label.py