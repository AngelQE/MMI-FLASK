"""
Datos de ejemplo ADICIONALES, coherentes con el reglamento:
  * un tutor para cada aula que aún no tenía
  * 2 a 4 estudiantes por aula, con la edad correcta al 31/03/2026 para su grado
  * familias (a veces con hermanos), matrículas 2026, calificaciones AD/A/B/C de los bimestres 1 y 2,
    conclusiones descriptivas, conducta, 20 días de asistencia, personas autorizadas y comunicados

Uso (después de python seed.py):   python seed_extra.py
Todas las familias entran con la clave  padre123  y los docentes nuevos con  docente123.
"""
import random
from datetime import date, timedelta
from flask import Flask
from flask_bcrypt import Bcrypt

from db import get_session
from models import (
    Rol, Usuario, Docente, Padre, Estudiante, EstudiantePadre, PersonaAutorizada, Grado, Aula, Area,
    Competencia, Matricula, Calificacion, ConclusionDescriptiva, EvaluacionConducta, NivelLogro, Nivel,
    Asistencia, EstadoAsistencia, Justificacion, EstadoJustificacion, Comunicado,
)

random.seed(2026)          # mismos datos cada vez que se ejecuta
app = Flask(__name__)
bcrypt = Bcrypt(app)
s = get_session()

if s.query(Rol).count() == 0:
    raise SystemExit("Primero corre:  python seed.py")
if s.query(Usuario).filter_by(email="familia.huaman@correo.com").first():
    raise SystemExit("Los datos extra ya fueron cargados.")

hash_docente = bcrypt.generate_password_hash("docente123").decode()
hash_padre = bcrypt.generate_password_hash("padre123").decode()
r_doc = s.query(Rol).filter_by(nombre="Docente").first()
r_pad = s.query(Rol).filter_by(nombre="Padre/Tutor").first()
u_admin = s.query(Usuario).join(Rol).filter(Rol.nombre == "Administrador").first()

# ------------------------------------------------------------------
# 1) Tutores para las aulas que no tenían
# ------------------------------------------------------------------
TUTORES = [  # (nombre, correo, especialidad, aula (grado, sección))
    ("Elena Rojas", "e.rojas@mimundoinfantil.com", "Educación Inicial", ("4 años", "B")),
    ("Patricia Salas", "p.salas@mimundoinfantil.com", "Educación Inicial", ("5 años", "A")),
    ("Gladys Ramos", "g.ramos@mimundoinfantil.com", "Educación Inicial", ("5 años", "B")),
    ("Miguel Ángel Cóndor", "m.condor@mimundoinfantil.com", "Educación Primaria", ("3° grado", "Única")),
    ("Sandra Huamán", "s.huaman@mimundoinfantil.com", "Educación Primaria", ("4° grado", "Única")),
    ("Jorge Ticona", "j.ticona@mimundoinfantil.com", "Educación Primaria", ("5° grado", "Única")),
    ("Liliana Paucar", "l.paucar@mimundoinfantil.com", "Educación Primaria", ("6° grado", "Única")),
]
def aula_de(grado, seccion):
    return s.query(Aula).join(Grado).filter(Grado.nombre == grado, Aula.seccion == seccion).first()

for nombre, correo, esp, (g, sec) in TUTORES:
    u = Usuario(role_id=r_doc.id, nombre=nombre, email=correo, password=hash_docente)
    s.add(u); s.flush()
    d = Docente(usuario_id=u.id, especialidad=esp, telefono="9" + str(random.randint(10000000, 99999999)))
    s.add(d); s.flush()
    aula_de(g, sec).tutor_id = d.id
s.commit()

# ------------------------------------------------------------------
# 2) Familias y estudiantes (edad al 31/03/2026 = edad normativa del grado)
# ------------------------------------------------------------------
NOMBRES_F = ["Camila", "Luciana", "Valeria", "Fernanda", "Isabella", "Mía", "Renata", "Antonella", "Alessia", "Zoe", "Ximena", "Daniela"]
NOMBRES_M = ["Santiago", "Matías", "Diego", "Gael", "Sebastián", "Adrián", "Joaquín", "Bruno", "Dylan", "Ian", "Thiago", "Nicolás"]
FAMILIAS = [  # (apellido, nombre del padre/madre, parentesco, [(grado, sección), ...] de sus hijos)
    ("Huamán", "Rosa Huamán", "MADRE", [("3 años", "Única"), ("2° grado", "Única")]),
    ("Quispe", "Pedro Quispe", "PADRE", [("3 años", "Única")]),
    ("Cóndor", "Marleni Cóndor", "MADRE", [("4 años", "A"), ("6° grado", "Única")]),
    ("Palomino", "Jhon Palomino", "PADRE", [("4 años", "A")]),
    ("Ccora", "Sonia Ccora", "MADRE", [("4 años", "B")]),
    ("Mayta", "Raúl Mayta", "PADRE", [("4 años", "B"), ("1° grado", "Única")]),
    ("Vílchez", "Karina Vílchez", "MADRE", [("5 años", "A")]),
    ("Rivera", "Óscar Rivera", "PADRE", [("5 años", "A"), ("3° grado", "Única")]),
    ("Meza", "Yesenia Meza", "MADRE", [("5 años", "B")]),
    ("Alvarado", "Luis Alvarado", "PADRE", [("5 años", "B")]),
    ("Poma", "Julia Poma", "MADRE", [("1° grado", "Única"), ("4° grado", "Única")]),
    ("Ávila", "Walter Ávila", "PADRE", [("2° grado", "Única")]),
    ("Chávez", "Elsa Chávez", "MADRE", [("3° grado", "Única")]),
    ("Taipe", "Mario Taipe", "PADRE", [("4° grado", "Única"), ("5° grado", "Única")]),
    ("Landa", "Gloria Landa", "MADRE", [("5° grado", "Única")]),
    ("Zárate", "Eduardo Zárate", "PADRE", [("6° grado", "Única")]),
]
dni_n = 71000000
matriculas_nuevas = []
for ap, nombre_padre, parentesco, hijos in FAMILIAS:
    u = Usuario(role_id=r_pad.id, nombre=nombre_padre, email=f"familia.{ap.lower().replace('á','a').replace('í','i').replace('ó','o')}@correo.com",
                password=hash_padre)
    s.add(u); s.flush()
    p = Padre(usuario_id=u.id, telefono="9" + str(random.randint(10000000, 99999999)),
              direccion=random.choice(["Av. Ferrocarril", "Jr. Real", "Calle Lima", "Av. Giráldez", "Jr. Ica", "Av. Mariscal Castilla"]) + f" {random.randint(100, 999)}, Huancayo")
    s.add(p); s.flush()
    for g, sec in hijos:
        edad = aula_de(g, sec).grado.edad_normativa
        nac = date(2025 - edad, random.randint(4, 12), random.randint(1, 28))   # cumple edad 'edad' al 31/03/2026
        dni_n += 1
        nombre = random.choice(NOMBRES_F if random.random() < .5 else NOMBRES_M)
        e = Estudiante(nombre=nombre, apellido=f"{ap} {random.choice(['Soto', 'Lazo', 'Cano', 'Rojas', 'Vega', 'Pérez', 'Gamarra'])}",
                       fecha_nacimiento=nac, dni_documento=str(dni_n))
        s.add(e); s.flush()
        s.add(EstudiantePadre(estudiante_id=e.id, padre_id=p.id, parentesco=parentesco))
        m = Matricula(estudiante_id=e.id, aula_id=aula_de(g, sec).id, anio_lectivo=2026, estado="activo")
        s.add(m); s.flush()
        matriculas_nuevas.append(m)
        # Persona autorizada de ejemplo para la mayoría
        if random.random() < .7:
            s.add(PersonaAutorizada(estudiante_id=e.id,
                                    nombre_completo=random.choice(["Carmen", "Teodora", "Julio", "Elvira", "Víctor", "Nelly"]) + f" {ap}",
                                    dni=str(random.randint(20000000, 49999999)),
                                    parentesco_o_relacion=random.choice(["Abuela", "Abuelo", "Tía", "Tío", "Hermana mayor"]),
                                    telefono="9" + str(random.randint(10000000, 99999999)), registrado_por_id=u.id))
        # Salida autónoma solo para los más grandes (5° y 6°), como ejemplo
        if g in ("5° grado", "6° grado") and random.random() < .5:
            e.salida_autonoma = True
s.commit()

# ------------------------------------------------------------------
# 3) Calificaciones (bimestres 1 y 2) para TODOS los matriculados 2026, conducta y asistencia
# ------------------------------------------------------------------
PESOS = [NivelLogro.AD] * 1 + [NivelLogro.A] * 6 + [NivelLogro.B] * 3 + [NivelLogro.C] * 1   # mayoría 'A'
CONCLUSIONES = {
    "A": "Muestra un desempeño esperado; participa con interés y cumple las actividades con acompañamiento oportuno.",
    "B": "Está en proceso de lograr lo esperado; necesita reforzar con actividades de práctica y apoyo del docente.",
    "C": "Se encuentra en inicio; requiere acompañamiento constante y apoyo adicional en casa para avanzar.",
}
todas = s.query(Matricula).filter_by(anio_lectivo=2026, estado="activo").all()
for m in todas:
    nivel = m.aula.grado.nivel
    exigen = {"A", "B", "C"} if nivel == Nivel.inicial else {"B", "C"}
    tutor_user = m.aula.tutor.usuario_id if m.aula.tutor else None
    areas = s.query(Area).filter_by(nivel=nivel).all()
    for bim in (1, 2):
        for area in areas:
            ya = {c.competencia_id for c in s.query(Calificacion).filter_by(matricula_id=m.id, bimestre=bim)}
            valores = []
            for comp in area.competencias:
                if comp.id in ya:
                    continue
                v = random.choice(PESOS)
                valores.append(v.value)
                s.add(Calificacion(matricula_id=m.id, competencia_id=comp.id, bimestre=bim, nivel_logro=v, registrado_por_id=tutor_user))
            peor = next((x for x in ("C", "B", "A") if x in valores), None)
            existe = s.query(ConclusionDescriptiva).filter_by(matricula_id=m.id, area_id=area.id, bimestre=bim).first()
            if peor and peor in exigen and not existe:
                s.add(ConclusionDescriptiva(matricula_id=m.id, area_id=area.id, bimestre=bim, texto=CONCLUSIONES[peor]))
        if not s.query(EvaluacionConducta).filter_by(matricula_id=m.id, bimestre=bim).first():
            r = lambda: random.choice([NivelLogro.AD, NivelLogro.A, NivelLogro.A, NivelLogro.A, NivelLogro.B])
            s.add(EvaluacionConducta(matricula_id=m.id, bimestre=bim, comportamiento=r(), puntualidad=r(),
                                     presentacion_personal=r(), registrado_por_id=tutor_user))

# Asistencia: últimos 20 días hábiles (solo para quien aún no tiene registro ese día)
dias, d = [], date.today()
while len(dias) < 20:
    d -= timedelta(days=1)
    if d.weekday() < 5:
        dias.append(d)
ausencias_para_justificar = []
for m in todas:
    for dia in dias:
        if s.query(Asistencia).filter_by(estudiante_id=m.estudiante_id, fecha=dia).first():
            continue
        x = random.random()
        estado = EstadoAsistencia.presente if x < .86 else EstadoAsistencia.tardanza if x < .93 else EstadoAsistencia.ausente
        a = Asistencia(estudiante_id=m.estudiante_id, fecha=dia, estado=estado)
        s.add(a)
        if estado == EstadoAsistencia.ausente:
            ausencias_para_justificar.append(a)
s.flush()
motivos = ["Cuadro de gripe", "Cita médica", "Viaje familiar por motivo urgente", "Malestar estomacal"]
for i, a in enumerate(ausencias_para_justificar[:6]):
    estado = [EstadoJustificacion.pendiente, EstadoJustificacion.aprobado, EstadoJustificacion.rechazado][i % 3]
    s.add(Justificacion(asistencia_id=a.id, motivo=random.choice(motivos), estado=estado))
    if estado == EstadoJustificacion.aprobado:
        a.estado = EstadoAsistencia.justificado

# ------------------------------------------------------------------
# 4) Comunicados
# ------------------------------------------------------------------
for titulo, texto in [
    ("Entrega del informe de progreso del I bimestre", "Se entregará el informe de progreso del primer bimestre en reunión con cada tutor. Es importante la asistencia de los padres."),
    ("Recordatorio de puntualidad", "Se recuerda que el ingreso es a las 8:00 a. m. (Primaria) y 8:30 a. m. (Inicial). La puntualidad se evalúa en la conducta."),
    ("Simulacro de sismo", "El jueves se realizará el simulacro de sismo. Los padres no deben acudir al colegio durante el ejercicio."),
    ("Actualización de personas autorizadas", "Verifica en el sistema que las personas autorizadas para recoger a tu hijo/a estén actualizadas. Sin autorización registrada no se entregará al estudiante."),
]:
    s.add(Comunicado(titulo=titulo, contenido=texto, emisor_id=u_admin.id))

s.commit()
total = s.query(Matricula).filter_by(anio_lectivo=2026).count()
print(f"Listo. Ahora hay {total} estudiantes matriculados en 2026.")
print("Familias:   familia.<apellido>@correo.com / padre123   (ej. familia.huaman@correo.com)")
print("Tutores nuevos: e.rojas@, p.salas@, g.ramos@, m.condor@, s.huaman@, j.ticona@, l.paucar@  (@mimundoinfantil.com) / docente123")
s.close()
