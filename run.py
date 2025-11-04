from app import create_app

# Creamos la instancia de la app llamando a la "factory"
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)