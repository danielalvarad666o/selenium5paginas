import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup
import pandas as pd
import os
import time

# Configuración del ChromeDriver
chrome_driver_path = "C:\\chromedrive\\chromedriver.exe"
chrome_options = Options()
chrome_service = Service(chrome_driver_path)

# Leer el archivo JSON de configuración
config_file = 'confi.json'
with open(config_file, 'r', encoding='utf-8') as file:
    config = json.load(file)

def remove_duplicates(data):
    return [dict(t) for t in {tuple(d.items()) for d in data}]


def save_data_to_excel(data, exel_name):
    df = pd.DataFrame(data)
    file_name = f"{exel_name}.xlsx"

    # Si el archivo ya existe, añadir los nuevos datos al final
    if os.path.exists(file_name):
        existing_df = pd.read_excel(file_name)
        df = pd.concat([existing_df, df], ignore_index=True)
    df.drop_duplicates(inplace=True)
    df.to_excel(file_name, index=False)
    print(f"Datos guardados en {file_name}")

def extract_div_data(driver, buscar, propiedad, extraer, exel_name):
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    identifier_type, identifier = propiedad.split(":")
    if identifier_type == 'class':
        divs = soup.find_all(buscar, class_=identifier)
    else:
        divs = soup.find_all(buscar, id=identifier)

    data = []
    for div in divs:
        item_data = {}
        tema = None
        
        for campo in extraer:
            if campo.get("campo") == "Tema":
                field_selector = campo.get("selector")
                element = div.select_one(field_selector)
                if element:
                    tema = element.text.strip()
                    item_data["Tema"] = tema
                    break

        if not tema:
            continue

        for campo in extraer:
            field_selector = campo.get("selector")
            atributo = campo.get("atributo", None)
            campo_nombre = campo.get("campo",None)
            element = div.select_one(field_selector)
            if element:
                field_value = element.get(atributo) if atributo else element.text.strip()
                item_data[campo_nombre] = field_value

        data.append(item_data)

    save_data_to_excel(data, exel_name)

def extract_table_data(driver, buscar, propiedad, extraer, exel_name):
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    if propiedad:
        identifier_type, identifier = propiedad.split(":")
        if identifier_type == 'id':
            table = soup.find(buscar, id=identifier)
        elif identifier_type == 'class':
            table = soup.find(buscar, class_=identifier)
    else:
        table = soup.find(buscar)

    if not table:
        print(f"No se encontró la tabla {exel_name}")
        return

    data = []
    if extraer:
        for item in table.find_all(buscar):
            item_data = {}
            for campo in extraer:
                field_selector = campo.get("selector")
                atributo = campo.get("atributo", None)
                campo_nombre = campo.get("campo",None)
                
                if atributo:
                    field_value = item.find(field_selector).get(atributo)
                else:
                    field_value = item.find(field_selector).text.strip()
                    
                item_data[campo_nombre] = field_value
            
            data.append(item_data)
    else:
        headers = [header.text for header in table.find_all('th')]
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            cols = [col.text.strip() for col in cols]
            data.append(cols)

    save_data_to_excel(data, exel_name)

def handle_pagination(driver, paginacion, buscar, propiedad, extraer, exel_name):
    xpath_pagina_siguiente = paginacion.get("xpath_pagina_siguiente")
    numero_maximo_paginas = paginacion.get("numero_maximo_paginas")

    current_page = 1
    while current_page <= numero_maximo_paginas:
        print(f"Extrayendo datos de la página {current_page}")
        if "table" in buscar:
            extract_table_data(driver, buscar, propiedad, extraer, f"{exel_name}_pagina_{current_page}")
        else:
            extract_div_data(driver, buscar, propiedad, extraer, f"{exel_name}_pagina_{current_page}")

        try:
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//{xpath_pagina_siguiente}"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            next_button.click()
            time.sleep(5)  # Esperar a que la página cargue completamente
            current_page += 1
        except Exception as e:
            print(f"No se pudo encontrar el botón de siguiente página o error: {e}")
            break

def handle_scroll(driver, buscar, propiedad, extraer, exel_name):
    SCROLL_PAUSE_TIME = 2
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        if "table" in buscar:
            extract_table_data(driver, buscar, propiedad, extraer, exel_name)
        else:
            extract_div_data(driver, buscar, propiedad, extraer, exel_name)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def handle_form(driver, formulario):
    form_selector = formulario.get("selector")
    campos = formulario.get("campos", [])

    if form_selector:
        retry_count = 3
        while retry_count > 0:
            try:
                form_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, form_selector))
                )
                for campo in campos:
                    nombre_campo = campo.get("campo")
                    valor_campo = campo.get("valor")

                    if nombre_campo:
                        field_element = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.NAME, nombre_campo))
                        )

                        if field_element.tag_name == "select":
                            select_element = Select(field_element)
                            select_element.select_by_visible_text(valor_campo)
                            WebDriverWait(driver, 10).until(
                                EC.text_to_be_present_in_element((By.TAG_NAME, "body"), valor_campo)
                            )
                        else:
                            field_element.clear()
                            field_element.send_keys(valor_campo)

                retry_count = 0
                print(f"Formulario procesado para la asignatura {valor_campo}")

            except Exception as e:
                print(f"Error al procesar el formulario: {e}")
                retry_count -= 1
                if retry_count == 0:
                    print("Máximos reintentos alcanzados, falló la operación")
                else:
                    print("Reintentando...")

def process_actions(driver, acciones):
    for accion in acciones:
        formulario = accion.get("formulario")
        asignatura_esperada = None
        if formulario:
            handle_form(driver, formulario)
            asignatura_esperada = next(
                (campo.get("valor") for campo in formulario.get("campos", []) if campo.get("campo") == "asignatura"), None
            )

        selector = accion.get("selector")
        if selector:
            try:
                elemento = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//{selector}"))
                )
                elemento.click()
                time.sleep(3)  # Esperar a que la página cargue completamente
                print(f"Clic en enlace: {selector}")
            except Exception as e:
                print(f"Error al hacer clic en el enlace: {selector}, Error: {e}")

        buscar = accion.get("buscar")
        propiedad = accion.get("propiedad")
        exel_name = accion.get("exel")
        extraer = accion.get("extraer", [])
        scroll = accion.get("scroll", False)
        tiene_paginacion = "paginacion" in accion

        if buscar and exel_name:
            if scroll:
                handle_scroll(driver, buscar, propiedad, extraer, exel_name)
            elif tiene_paginacion:
                paginacion = accion.get("paginacion")
                handle_pagination(driver, paginacion, buscar, propiedad, extraer, exel_name)
            else:
                if "table" in buscar:
                    extract_table_data(driver, buscar, propiedad, extraer, exel_name)
                else:
                    extract_div_data(driver, buscar, propiedad, extraer, exel_name)

def main():
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    try:
        for site in config:
            url = site.get("url")
            acciones = site.get("acciones")
            driver.get(url)
            if acciones:
                print(f"Procesando acciones en {url}")
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                process_actions(driver, acciones)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
