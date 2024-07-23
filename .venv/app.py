from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, MetaData, Table, select, and_, not_
from sqlalchemy.orm import sessionmaker
import random

app = Flask(__name__)
CORS(app, resources={r"/generar_plan_dieta": {"origins": "https://nutrigobo.netlify.app"}})

# Configura la conexión a la base de datos MySQL
DATABASE_URL = 'mysql+pymysql://root:GVXTrEcCpDqaLAjUroKuHKwndblPTcOv@roundhouse.proxy.rlwy.net:20735/railway'
engine = create_engine(DATABASE_URL)
metadata = MetaData()
Session = sessionmaker(bind=engine)
session = Session()

# Cargar la tabla de recetas
recetas_table = Table('recetas', metadata, autoload_with=engine)

def calcular_tmb(peso, altura, edad, sexo):
    if sexo == 'Masculino':
        return 88.362 + (13.397 * peso) + (4.799 * altura) - (5.677 * edad)
    else:
        return 447.593 + (9.247 * peso) + (3.098 * altura) - (4.330 * edad)

def calcular_tdee(tmb, nivel_actividad):
    factores_actividad = {
        'Sedentario': 1.2,
        'Ligero': 1.375,
        'Moderado': 1.55,
        'Activo': 1.725,
        'Muy Activo': 1.9
    }
    return tmb * factores_actividad[nivel_actividad]

def calcular_macronutrientes(tdee):
    proteinas = 0.20 * tdee / 4  # 20% de las calorías diarias, 1g de proteínas = 4 calorías
    carbohidratos = 0.55 * tdee / 4  # 55% de las calorías diarias, 1g de carbohidratos = 4 calorías
    grasas = 0.25 * tdee / 9  # 25% de las calorías diarias, 1g de grasas = 9 calorías
    return proteinas, carbohidratos, grasas

def filtrar_recetas(restricciones, tipo_comida_id):
    query = select(
        recetas_table.c.id,
        recetas_table.c.nombre,
        recetas_table.c.calorias,
        recetas_table.c.proteinas,
        recetas_table.c.carbohidratos,
        recetas_table.c.grasas,
        recetas_table.c.ingredientes,
        recetas_table.c.instrucciones,
        recetas_table.c.habilitado,
        recetas_table.c.tipo_comida_id,
        recetas_table.c.created_at,
        recetas_table.c.updated_at
    ).where(
        and_(
            recetas_table.c.habilitado == True,
            not_(recetas_table.c.ingredientes.ilike(f"%{restricciones}%")),
            recetas_table.c.tipo_comida_id == tipo_comida_id
        )
    )
    return session.execute(query).fetchall()

def seleccionar_recetas(recetas, calorias_max, cantidad):
    seleccionadas = []
    calorias_totales = 0

    while calorias_totales < calorias_max and recetas:
        receta = random.choice(recetas)
        if calorias_totales + receta.calorias <= calorias_max:
            seleccionadas.append(receta)
            calorias_totales += receta.calorias
        recetas.remove(receta)

    return seleccionadas

def calcular_nutricion(plan_dieta):
    calorias_totales = sum(r.calorias for comida in plan_dieta.values() for r in comida)
    proteinas_totales = sum(r.proteinas for comida in plan_dieta.values() for r in comida)
    carbohidratos_totales = sum(r.carbohidratos for comida in plan_dieta.values() for r in comida)
    grasas_totales = sum(r.grasas for comida in plan_dieta.values() for r in comida)
    return round(calorias_totales, 2), round(proteinas_totales, 2), round(carbohidratos_totales, 2), round(grasas_totales, 2)


def calcular_calorias(usuario):
    if usuario["sexo"] == "Masculino":
        bmr = 10 * usuario["peso"] + 6.25 * usuario["altura"] - 5 * usuario["edad"] + 5
    else:
        bmr = 10 * usuario["peso"] + 6.25 * usuario["altura"] - 5 * usuario["edad"] - 161

    if usuario["nivel_actividad"] == "Sedentario":
        calorias = bmr * 1.2
    elif usuario["nivel_actividad"] == "Ligero":
        calorias = bmr * 1.375
    elif usuario["nivel_actividad"] == "Moderado":
        calorias = bmr * 1.55
    elif usuario["nivel_actividad"] == "Activo":
        calorias = bmr * 1.725
    else:
        calorias = bmr * 1.9

    return calorias


def ajustar_alimentos_niveles(usuario, alimentos):
    if usuario["colesterol_total"] > 200 or usuario["colesterol_ldl"] > 100:
        # Reducir alimentos altos en colesterol y grasas saturadas
        alimentos["desayuno"] = [item for item in alimentos["desayuno"] if item not in ["huevos"]]
        alimentos["almuerzo"] = [item for item in alimentos["almuerzo"] if item not in ["pollo frito"]]
        alimentos["cena"] = [item for item in alimentos["cena"] if item not in ["pollo frito"]]

    if usuario["glucosa_ayunas"] > 100:
        # Reducir alimentos altos en azúcares simples
        alimentos["desayuno"] = [item for item in alimentos["desayuno"] if item not in ["jugo de naranja"]]
        alimentos["snack"] = [item for item in alimentos["snack"] if item not in ["barras de cereal"]]

    if usuario["trigliceridos"] > 150:
        # Reducir alimentos altos en grasas y azúcares
        alimentos["snack"] = [item for item in alimentos["snack"] if item not in ["batido de proteínas"]]
        alimentos["almuerzo"] = [item for item in alimentos["almuerzo"] if item not in ["arroz integral"]]

    return alimentos

@app.route('/generar_plan_dieta', methods=['POST'])
def generar_plan_dieta():
    datos_usuario = request.json
    print('Datos recibidos:', datos_usuario)  # Verificar datos recibidos

    nombre = datos_usuario.get('nombre')
    edad = datos_usuario.get('edad')
    sexo = datos_usuario.get('sexo')
    peso = datos_usuario.get('peso')
    altura = datos_usuario.get('altura')
    nivel_actividad = datos_usuario.get('nivel_actividad')
    circunferencia_cintura = datos_usuario.get('circunferencia_cintura')
    circunferencia_caderas = datos_usuario.get('circunferencia_caderas')
    glucosa_ayunas = datos_usuario.get('glucosa_ayunas')
    colesterol_total = datos_usuario.get('colesterol_total')
    colesterol_hdl = datos_usuario.get('colesterol_hdl')
    colesterol_ldl = datos_usuario.get('colesterol_ldl')
    trigliceridos = datos_usuario.get('trigliceridos')
    hemoglobina = datos_usuario.get('hemoglobina')
    alergias_alimentarias = datos_usuario.get('alergias_alimentarias')
    restricciones_dieteticas = datos_usuario.get('restricciones_dieteticas')
    preferencias_alimenticias = datos_usuario.get('preferencias_alimenticias')
    dias = datos_usuario.get('dias')

    # Conversión de tipos
    try:
        edad = int(edad)
        peso = float(peso)
        altura = float(altura)
    except ValueError as e:
        return jsonify({"error": f"Error en la conversión de valores: {e}"}), 400

    # Verificar tipos de datos después de la conversión
    print(f"Edad: {type(edad)}, Peso: {type(peso)}, Altura: {type(altura)}")

    # Calcular TMB y TDEE
    tmb = calcular_tmb(peso, altura, edad, sexo)
    tdee = calcular_tdee(tmb, nivel_actividad)
    proteinas, carbohidratos, grasas = calcular_macronutrientes(tdee)

    plan_dieta_completo = []

    for dia in range(dias):
        desayunos = filtrar_recetas(restricciones_dieteticas, 1)
        almuerzos = filtrar_recetas(restricciones_dieteticas, 2)
        cenas = filtrar_recetas(restricciones_dieteticas, 3)

        desayuno = seleccionar_recetas(desayunos, tdee * 0.3, 3)  # Seleccionar varias recetas hasta 30% de las calorías diarias para el desayuno
        almuerzo = seleccionar_recetas(almuerzos, tdee * 0.4, 3)  # Seleccionar varias recetas hasta 40% de las calorías diarias para el almuerzo
        cena = seleccionar_recetas(cenas, tdee * 0.3, 3)  # Seleccionar varias recetas hasta 30% de las calorías diarias para la cena

        plan_dieta = {
            "desayuno": desayuno,
            "almuerzo": almuerzo,
            "cena": cena
        }

        calorias, proteinas_totales, carbohidratos_totales, grasas_totales = calcular_nutricion(plan_dieta)
        plan_dieta_completo.append({
            "dia": dia + 1,
            "plan_dieta": {
                "desayuno": [dict(r._mapping) for r in plan_dieta["desayuno"]],
                "almuerzo": [dict(r._mapping) for r in plan_dieta["almuerzo"]],
                "cena": [dict(r._mapping) for r in plan_dieta["cena"]]
            },
            "calorias_totales": f"{calorias:.2f}",
            "proteinas_totales": f"{proteinas_totales:.2f}",
            "carbohidratos_totales": f"{carbohidratos_totales:.2f}",
            "grasas_totales": f"{grasas_totales:.2f}"
        })

    return jsonify(plan_dieta_completo)


if __name__ == '__main__':
    app.run(debug=True)
