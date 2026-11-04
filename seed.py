"""
Carga el catálogo REAL del Reglamento Interno 2026 (grados, aulas, áreas, competencias)
y datos de demostración (usuarios, estudiantes, matrículas, calificaciones...).

Correr una sola vez:  python seed.py
"""
from datetime import date, time, timedelta
from flask import Flask
from flask_bcrypt import Bcrypt

from db import get_session
from models import (
    Rol, Usuario, Docente, Padre, Estudiante, EstudiantePadre, PersonaAutorizada,
    Grado, Aula, Area, Competencia, AsignacionDocente, Matricula,
    Calificacion, ConclusionDescriptiva, EvaluacionConducta,
    Asistencia, EstadoAsistencia, Justificacion, EstadoJustificacion,
    EntradaSalida, TipoMovimiento, Comunicado, Nivel, NivelLogro,
)

app = Flask(__name__)
bcrypt = Bcrypt(app)
clave = lambda t: bcrypt.generate_password_hash(t).decode("utf-8")

s = get_session()
if s.query(Rol).count() > 0:
    print("Ya hay datos cargados, no se vuelve a sembrar.")
    raise SystemExit

# ------------------------------------------------------------------
# CATÁLOGO REAL (Reglamento Interno 2026)
# ------------------------------------------------------------------
# Anexo 2 (edades) + Art. 69 (horarios): nivel, nombre, ciclo, edad normativa, edad máx., ingreso, salida
GRADOS = [
    (Nivel.inicial,  "3 años",    "II",  3, 5,  time(8, 30), time(13, 0)),
    (Nivel.inicial,  "4 años",    "II",  4, 6,  time(8, 30), time(13, 10)),
    (Nivel.inicial,  "5 años",    "II",  5, 7,  time(8, 30), time(13, 20)),
    (Nivel.primaria, "1° grado",  "III", 6, 8,  time(8, 0),  time(13, 30)),
    (Nivel.primaria, "2° grado",  "III", 7, 9,  time(8, 0),  time(13, 30)),
    (Nivel.primaria, "3° grado",  "IV",  8, 10, time(8, 0),  time(13, 40)),
    (Nivel.primaria, "4° grado",  "IV",  9, 11, time(8, 0),  time(13, 40)),
    (Nivel.primaria, "5° grado",  "V",   10, 12, time(8, 0), time(13, 50)),
    (Nivel.primaria, "6° grado",  "V",   11, 13, time(8, 0), time(13, 50)),
]
grados = {}
for nivel, nombre, ciclo, en, em, hi, hs in GRADOS:
    g = Grado(nivel=nivel, nombre=nombre, ciclo=ciclo, edad_normativa=en, edad_maxima=em, hora_ingreso=hi, hora_salida=hs)
    s.add(g)
    grados[nombre] = g
s.commit()

# Art. 82: aulas y capacidad máxima 2026
AULAS = [("3 años", "Única", 25), ("4 años", "A", 25), ("4 años", "B", 25), ("5 años", "A", 25), ("5 años", "B", 25),
         ("1° grado", "Única", 25), ("2° grado", "Única", 25), ("3° grado", "Única", 25),
         ("4° grado", "Única", 20), ("5° grado", "Única", 20), ("6° grado", "Única", 20)]
aulas = {}
for grado, seccion, cap in AULAS:
    a = Aula(grado_id=grados[grado].id, seccion=seccion, capacidad_maxima=cap)
    s.add(a)
    aulas[(grado, seccion)] = a
s.commit()

# Anexo 3: plan de estudios (áreas y competencias)
TRANSVERSALES = ["Se desenvuelve en entornos virtuales generados por las TIC",
                 "Gestiona su aprendizaje de manera autónoma"]
PLAN = {
    Nivel.inicial: {      # 13 competencias
        "Personal Social": ["Construye su identidad",
                            "Convive y participa democráticamente en la búsqueda del bien común"],
        "Educación Religiosa": ["Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente, comprendiendo la doctrina de su propia religión, abierto al diálogo con las que le son cercanas"],
        "Psicomotriz": ["Se desenvuelve de manera autónoma a través de su motricidad"],
        "Comunicación": ["Se comunica oralmente en su lengua materna",
                         "Lee diversos tipos de textos en su lengua materna",
                         "Escribe diversos tipos de textos en su lengua materna"],
        "Arte y Cultura": ["Crea proyectos desde los lenguajes artísticos"],
        "Matemática": ["Resuelve problemas de cantidad",
                       "Resuelve problemas de forma, movimiento y localización"],
        "Ciencia y Tecnología": ["Indaga mediante métodos científicos para construir sus conocimientos"],
    },
    Nivel.primaria: {     # 8 áreas, 27 competencias (con las 2 transversales)
        "Personal Social": ["Construye su identidad",
                            "Convive y participa democráticamente en la búsqueda del bien común",
                            "Construye interpretaciones históricas",
                            "Gestiona responsablemente el espacio y el ambiente",
                            "Gestiona responsablemente los recursos económicos"],
        "Educación Religiosa": ["Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente, comprendiendo la doctrina de su propia religión, abierto al diálogo con las que le son cercanas",
                                "Asume la experiencia del encuentro personal y comunitario con Dios en su proyecto de vida en coherencia con su creencia religiosa"],
        "Educación Física": ["Se desenvuelve de manera autónoma a través de su motricidad",
                             "Asume una vida saludable",
                             "Interactúa a través de sus habilidades sociomotrices"],
        "Comunicación": ["Se comunica oralmente en su lengua materna",
                         "Lee diversos tipos de textos escritos en su lengua materna",
                         "Escribe diversos tipos de textos en su lengua materna"],
        "Arte y Cultura": ["Aprecia de manera crítica manifestaciones artístico-culturales",
                           "Crea proyectos desde los lenguajes artísticos"],
        "Inglés": ["Se comunica oralmente en inglés como lengua extranjera",
                   "Lee diversos tipos de textos en inglés como lengua extranjera",
                   "Escribe diversos tipos de textos en inglés como lengua extranjera"],
        "Matemática": ["Resuelve problemas de cantidad",
                       "Resuelve problemas de regularidad, equivalencia y cambio",
                       "Resuelve problemas de forma, movimiento y localización",
                       "Resuelve problemas de gestión de datos e incertidumbre"],
        "Ciencia y Tecnología": ["Indaga mediante métodos científicos para construir sus conocimientos",
                                 "Explica el mundo físico basándose en conocimientos sobre los seres vivos; materia y energía; biodiversidad, Tierra y universo",
                                 "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno"],
    },
}
areas = {}
for nivel, plan in PLAN.items():
    for nombre_area, comps in plan.items():
        ar = Area(nombre=nombre_area, nivel=nivel)
        s.add(ar); s.flush()
        for c in comps:
            s.add(Competencia(area_id=ar.id, nombre=c))
        areas[(nivel, nombre_area)] = ar
    tr = Area(nombre="Competencias transversales", nivel=nivel, es_transversal=True)
    s.add(tr); s.flush()
    for c in TRANSVERSALES:
        s.add(Competencia(area_id=tr.id, nombre=c))
    areas[(nivel, "Competencias transversales")] = tr
s.commit()

# ------------------------------------------------------------------
# DATOS DE DEMOSTRACIÓN
# ------------------------------------------------------------------
r_admin = Rol(nombre="Administrador", descripcion="Dirección: acceso total al sistema")
r_doc = Rol(nombre="Docente", descripcion="Tutor/docente de aula: asistencia, calificaciones y conducta")
r_pad = Rol(nombre="Padre/Tutor", descripcion="Consulta la información de su hijo/a")
s.add_all([r_admin, r_doc, r_pad]); s.commit()

u_admin = Usuario(role_id=r_admin.id, nombre="Directora", email="admin@mimundoinfantil.com", password=clave("admin123"))
u_d1 = Usuario(role_id=r_doc.id, nombre="María Fernández", email="m.fernandez@mimundoinfantil.com", password=clave("docente123"))
u_d2 = Usuario(role_id=r_doc.id, nombre="Juan Pérez", email="j.perez@mimundoinfantil.com", password=clave("docente123"))
u_d3 = Usuario(role_id=r_doc.id, nombre="Rosa Quispe", email="r.quispe@mimundoinfantil.com", password=clave("docente123"))
u_d4 = Usuario(role_id=r_doc.id, nombre="Carlos Mendoza", email="c.mendoza@mimundoinfantil.com", password=clave("docente123"))
u_p1 = Usuario(role_id=r_pad.id, nombre="Carlos López", email="c.lopez@correo.com", password=clave("padre123"))
u_p2 = Usuario(role_id=r_pad.id, nombre="Ana Torres", email="a.torres@correo.com", password=clave("padre123"))
u_p3 = Usuario(role_id=r_pad.id, nombre="Luis Ramírez", email="l.ramirez@correo.com", password=clave("padre123"))
u_p4 = Usuario(role_id=r_pad.id, nombre="Lucía Vargas", email="l.vargas@correo.com", password=clave("padre123"))
s.add_all([u_admin, u_d1, u_d2, u_d3, u_d4, u_p1, u_p2, u_p3, u_p4]); s.commit()

d1 = Docente(usuario_id=u_d1.id, especialidad="Educación Inicial", telefono="987654321")
d2 = Docente(usuario_id=u_d2.id, especialidad="Educación Primaria", telefono="912345678")
d3 = Docente(usuario_id=u_d3.id, especialidad="Educación Inicial", telefono="933222111")
d4 = Docente(usuario_id=u_d4.id, especialidad="Inglés y Educación Física", telefono="944555666")
p1 = Padre(usuario_id=u_p1.id, telefono="987111222", direccion="Av. Los Jardines 123, Huancayo")
p2 = Padre(usuario_id=u_p2.id, telefono="987333444", direccion="Calle Las Flores 456, Huancayo")
p3 = Padre(usuario_id=u_p3.id, telefono="987555666", direccion="Jr. Los Pinos 789, Huancayo")
p4 = Padre(usuario_id=u_p4.id, telefono="987777888", direccion="Av. Giráldez 321, Huancayo")
s.add_all([d1, d2, d3, d4, p1, p2, p3, p4]); s.commit()

# Tutores de aula y asignación de áreas
aulas[("3 años", "Única")].tutor_id = d1.id
aulas[("4 años", "A")].tutor_id = d3.id
aulas[("1° grado", "Única")].tutor_id = d2.id
aulas[("2° grado", "Única")].tutor_id = d2.id
for g in ("1° grado", "2° grado"):
    for nombre_area in ("Inglés", "Educación Física"):
        s.add(AsignacionDocente(docente_id=d4.id, aula_id=aulas[(g, "Única")].id,
                                area_id=areas[(Nivel.primaria, nombre_area)].id))
s.commit()

# Estudiantes (edades al 31/03/2026 coherentes con su grado)
E = lambda n, a, f, dni: Estudiante(nombre=n, apellido=a, fecha_nacimiento=f, dni_documento=dni)
e_sofia = E("Sofía", "López", date(2019, 3, 15), "12345678")
e_mateo = E("Mateo", "Torres", date(2019, 7, 22), "23456789")
e_vale = E("Valentina", "Ramírez", date(2020, 1, 10), "34567890")
e_lucas = E("Lucas", "López", date(2020, 5, 5), "45678901")
e_emma = E("Emma", "Vargas", date(2022, 8, 1), "56789012")
e_thiago = E("Thiago", "Vargas", date(2021, 6, 10), "67890123")
s.add_all([e_sofia, e_mateo, e_vale, e_lucas, e_emma, e_thiago]); s.commit()

s.add_all([
    EstudiantePadre(estudiante_id=e_sofia.id, padre_id=p1.id, parentesco="PADRE"),
    EstudiantePadre(estudiante_id=e_lucas.id, padre_id=p1.id, parentesco="PADRE"),
    EstudiantePadre(estudiante_id=e_mateo.id, padre_id=p2.id, parentesco="MADRE"),
    EstudiantePadre(estudiante_id=e_vale.id, padre_id=p3.id, parentesco="TUTOR"),
    EstudiantePadre(estudiante_id=e_emma.id, padre_id=p4.id, parentesco="MADRE"),
    EstudiantePadre(estudiante_id=e_thiago.id, padre_id=p4.id, parentesco="MADRE"),
])

M = lambda e, a: Matricula(estudiante_id=e.id, aula_id=aulas[a].id, anio_lectivo=2026, estado="activo")
m_sofia = M(e_sofia, ("2° grado", "Única"))
m_mateo = M(e_mateo, ("1° grado", "Única"))
m_vale = M(e_vale, ("1° grado", "Única"))
m_lucas = M(e_lucas, ("5 años", "A"))
m_emma = M(e_emma, ("3 años", "Única"))
m_thiago = M(e_thiago, ("4 años", "A"))
s.add_all([m_sofia, m_mateo, m_vale, m_lucas, m_emma, m_thiago]); s.commit()

# Calificaciones de ejemplo (Bimestre 1): Comunicación y Matemática de Mateo y Valentina (1° grado)
def comps(nivel, nombre_area):
    return s.query(Competencia).filter_by(area_id=areas[(nivel, nombre_area)].id).all()

niveles_demo = {"Mateo": [NivelLogro.A, NivelLogro.AD, NivelLogro.B],
                "Valentina": [NivelLogro.A, NivelLogro.A, NivelLogro.A]}
for m, nombre in ((m_mateo, "Mateo"), (m_vale, "Valentina")):
    for i, c in enumerate(comps(Nivel.primaria, "Comunicación")):
        s.add(Calificacion(matricula_id=m.id, competencia_id=c.id, bimestre=1,
                           nivel_logro=niveles_demo[nombre][i], registrado_por_id=u_d2.id))
    for c in comps(Nivel.primaria, "Matemática"):
        s.add(Calificacion(matricula_id=m.id, competencia_id=c.id, bimestre=1,
                           nivel_logro=NivelLogro.A, registrado_por_id=u_d2.id))
s.add(ConclusionDescriptiva(matricula_id=m_mateo.id, area_id=areas[(Nivel.primaria, "Comunicación")].id, bimestre=1,
      texto="Mateo se expresa con claridad, pero necesita reforzar la escritura de textos breves con acompañamiento."))
for c in comps(Nivel.inicial, "Comunicación"):
    s.add(Calificacion(matricula_id=m_lucas.id, competencia_id=c.id, bimestre=1,
                       nivel_logro=NivelLogro.A, registrado_por_id=u_d3.id))
s.add(ConclusionDescriptiva(matricula_id=m_lucas.id, area_id=areas[(Nivel.inicial, "Comunicación")].id, bimestre=1,
      texto="Lucas dialoga con sus compañeros y reconoce algunas letras de su nombre."))
s.add(EvaluacionConducta(matricula_id=m_mateo.id, bimestre=1, comportamiento=NivelLogro.A,
                         puntualidad=NivelLogro.AD, presentacion_personal=NivelLogro.A, registrado_por_id=u_d2.id))

# Asistencia: últimos 5 días hábiles
def dias_habiles_atras(n):
    d, out = date.today(), []
    while len(out) < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out
dias = dias_habiles_atras(5)
asis_ausente = None
for i, dia in enumerate(dias):
    for m in (m_sofia, m_mateo, m_vale, m_lucas, m_emma, m_thiago):
        estado = EstadoAsistencia.presente
        if m is m_mateo and i == 2:
            estado = EstadoAsistencia.ausente
        if m is m_vale and i == 1:
            estado = EstadoAsistencia.tardanza
        a = Asistencia(estudiante_id=m.estudiante_id, fecha=dia, estado=estado)
        s.add(a)
        if m is m_mateo and i == 2:
            asis_ausente = a
s.commit()
s.add(Justificacion(asistencia_id=asis_ausente.id, motivo="Cita médica del estudiante", estado=EstadoJustificacion.pendiente))

# Seguridad: personas autorizadas y salida autónoma
pa1 = PersonaAutorizada(estudiante_id=e_sofia.id, nombre_completo="Rosa López", dni="55667788",
                        parentesco_o_relacion="Abuela", telefono="987000111", registrado_por_id=u_p1.id)
s.add(pa1)
e_sofia.salida_autonoma = False
e_thiago.tiene_nee = False
s.commit()

s.add_all([
    EntradaSalida(estudiante_id=e_sofia.id, tipo=TipoMovimiento.entrada, detalle="Ingreso normal"),
    EntradaSalida(estudiante_id=e_sofia.id, tipo=TipoMovimiento.salida, persona_autorizada_id=pa1.id,
                  detalle="Retirada por Rosa López (Abuela)"),
])
s.add_all([
    Comunicado(titulo="Reunión de padres de familia",
               contenido="Se invita a todos los padres de familia a la reunión general el viernes a las 4:00 p. m.",
               emisor_id=u_admin.id),
    Comunicado(titulo="Jornada deportiva",
               contenido="El viernes habrá jornada deportiva en el patio principal. Los estudiantes deben asistir con uniforme de educación física.",
               emisor_id=u_d4.id),
])
s.commit()
s.close()
print("Catálogo del reglamento + datos de demostración cargados.")
print("Dirección : admin@mimundoinfantil.com / admin123")
print("Docente   : m.fernandez@mimundoinfantil.com / docente123  (tutora de 3 años)")
print("Docente   : j.perez@mimundoinfantil.com / docente123      (tutor de 1° y 2° grado)")
print("Padre     : c.lopez@correo.com / padre123")
