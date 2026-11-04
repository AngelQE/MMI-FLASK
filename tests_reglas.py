"""
Pruebas automáticas de las reglas de negocio del Reglamento Interno.
Uso:  python seed.py (con base limpia)  y luego  python tests_reglas.py
"""
import datetime as dt
import app as A
from db import get_session
from models import (Estudiante, Aula, Grado, Matricula, Area, Nivel, Calificacion, Asistencia, EstadoAsistencia,
                    PersonaAutorizada, Usuario)

A.app.config["TESTING"] = True
ok = fail = 0


def cliente(correo, clave):
    c = A.app.test_client()
    assert c.post("/login", data={"correo": correo, "clave": clave}, follow_redirects=True).status_code == 200
    return c


def chequear(desc, cond):
    global ok, fail
    if cond:
        ok += 1; print("  ✔", desc)
    else:
        fail += 1; print("  ✘ FALLA:", desc)


# ---------------- PÚBLICO ----------------
print("\n[PÚBLICO]")
pub = A.app.test_client()
r = pub.get("/")
chequear("portada carga (200)", r.status_code == 200)
chequear("portada muestra horarios reales de Inicial y Primaria", b"08:30" in r.data and b"13:00" in r.data and b"08:00" in r.data)
chequear("CSS se sirve", pub.get("/static/css/estilo.css").status_code == 200)
chequear("sin sesión /dashboard redirige al login", pub.get("/dashboard").status_code == 302)
r = pub.post("/login", data={"correo": "admin@mimundoinfantil.com", "clave": "mala"})
chequear("clave incorrecta muestra error", b"incorrectos" in r.data)

# ---------------- ADMIN: pantallas ----------------
print("\n[ADMIN - pantallas]")
adm = cliente("admin@mimundoinfantil.com", "admin123")
rutas = ["/dashboard", "/usuarios", "/usuarios/nuevo", "/estudiantes", "/estudiantes/nuevo", "/estudiantes/1",
         "/estudiantes/1/asignar_padre", "/aulas", "/aulas/1", "/areas", "/matriculas", "/matriculas/nueva",
         "/calificaciones", "/conducta", "/asistencia", "/justificaciones", "/entrada_salida", "/comunicados",
         "/comunicados/nuevo", "/personas_autorizadas", "/personas_autorizadas/nueva"]
chequear(f"las {len(rutas)} pantallas de Dirección cargan (200)", all(adm.get(x).status_code == 200 for x in rutas))

# ---------------- MATRÍCULA ----------------
print("\n[MATRÍCULA - edad y capacidad]")
s = get_session()
aula_3ro = s.query(Aula).join(Grado).filter(Grado.nombre == "3° grado").first().id
aula_5b = s.query(Aula).join(Grado).filter(Grado.nombre == "5 años", Aula.seccion == "B").first().id
aula_3anios = s.query(Aula).join(Grado).filter(Grado.nombre == "3 años").first().id
p = Estudiante(nombre="Pedro", apellido="Test", fecha_nacimiento=dt.date(2020, 2, 1), dni_documento="99887766")
b = Estudiante(nombre="Nuevo", apellido="Bebé", fecha_nacimiento=dt.date(2022, 9, 9))
s.add_all([p, b]); s.commit(); pedro, bebe = p.id, b.id; s.close()

r = adm.post("/matriculas/nueva", data={"estudiante_id": pedro, "aula_id": aula_3ro, "anio_lectivo": 2026}, follow_redirects=True)
chequear("niño de 6 años NO entra a 3° grado (edad mínima 8)", "exige entre" in r.data.decode())
r = adm.post("/matriculas/nueva", data={"estudiante_id": pedro, "aula_id": aula_3ro, "anio_lectivo": 2026, "forzar": "on"}, follow_redirects=True)
chequear("con excepción autorizada por Dirección sí se matricula", "Matrícula registrada" in r.data.decode())
r = adm.post("/matriculas/nueva", data={"estudiante_id": pedro, "aula_id": aula_5b, "anio_lectivo": 2026, "forzar": "on"}, follow_redirects=True)
chequear("no permite 2 matrículas del mismo estudiante en el mismo año", "ya tiene una matrícula" in r.data.decode())
s = get_session(); a = s.get(Aula, aula_3anios)
a.capacidad_maxima = len([m for m in a.matriculas if m.anio_lectivo == 2026]); s.commit(); s.close()
r = adm.post("/matriculas/nueva", data={"estudiante_id": bebe, "aula_id": aula_3anios, "anio_lectivo": 2026}, follow_redirects=True)
chequear("aula llena bloquea la matrícula (capacidad máxima, Art. 82)", "capacidad máxima" in r.data.decode())

# ---------------- CALIFICACIONES ----------------
print("\n[CALIFICACIONES - AD/A/B/C y permisos por área]")
perez = cliente("j.perez@mimundoinfantil.com", "docente123")      # tutor de 1° y 2° grado
mendoza = cliente("c.mendoza@mimundoinfantil.com", "docente123")  # Inglés y Ed. Física en 1° y 2°
maria = cliente("m.fernandez@mimundoinfantil.com", "docente123")  # tutora de 3 años
s = get_session()
aula1 = s.query(Aula).join(Grado).filter(Grado.nombre == "1° grado").first().id
mateo_m = [m for m in s.query(Matricula).filter_by(aula_id=aula1, anio_lectivo=2026) if m.estudiante.nombre == "Mateo"][0].id
area_mat = s.query(Area).filter_by(nombre="Matemática", nivel=Nivel.primaria).first()
area_ing = s.query(Area).filter_by(nombre="Inglés", nivel=Nivel.primaria).first()
comp_mat = [c.id for c in area_mat.competencias]
a_mat, a_ing = area_mat.id, area_ing.id
s.close()

r = perez.get(f"/calificaciones?aula_id={aula1}&area_id={a_mat}&bimestre=2")
chequear("el tutor ve la cuadrícula de Matemática de su aula", b"Resuelve problemas de cantidad" in r.data)
datos = {"aula_id": aula1, "area_id": a_mat, "bimestre": 2}
for i, c in enumerate(comp_mat):
    datos[f"n_{mateo_m}_{c}"] = ["AD", "B", "C", "X"][i]   # 'X' es inválido a propósito
txt = perez.post("/calificaciones", data=datos, follow_redirects=True).data.decode()
chequear("guarda las calificaciones", "guardadas" in txt)
chequear("avisa que falta la conclusión descriptiva (Art. 133) cuando hay B o C", "conclusión descriptiva de" in txt and "Mateo" in txt)
s = get_session()
g = {c.competencia_id: c.nivel_logro.value for c in s.query(Calificacion).filter_by(matricula_id=mateo_m, bimestre=2)}
s.close()
chequear("AD / B / C quedan guardados correctamente", [g.get(c) for c in comp_mat[:3]] == ["AD", "B", "C"])
chequear("valor inválido 'X' se ignora", comp_mat[3] not in g)
r = mendoza.get(f"/calificaciones?aula_id={aula1}&area_id={a_mat}&bimestre=1")
chequear("docente de Inglés NO puede calificar Matemática", b"Resuelve problemas de cantidad" not in r.data)
r = mendoza.get(f"/calificaciones?aula_id={aula1}&area_id={a_ing}&bimestre=1")
chequear("docente de Inglés SÍ puede calificar Inglés", b"Se comunica oralmente en ingl" in r.data)
r = maria.get(f"/calificaciones?aula_id={aula1}&area_id={a_mat}")
chequear("tutora de 3 años NO puede calificar el aula de 1°", b"Resuelve problemas de cantidad" not in r.data)
chequear("tutora de 3 años NO ve la ficha del aula de 1° (403)", maria.get(f"/aulas/{aula1}").status_code == 403)

# ---------------- CONDUCTA ----------------
print("\n[CONDUCTA]")
r = perez.post("/conducta", data={"aula_id": aula1, "bimestre": 2, f"comp_{mateo_m}": "A", f"punt_{mateo_m}": "AD", f"pres_{mateo_m}": "B"}, follow_redirects=True)
chequear("el tutor guarda la conducta", "guardada" in r.data.decode())
chequear("docente que NO es tutor no puede evaluar conducta", b"Mateo" not in mendoza.get(f"/conducta?aula_id={aula1}").data)

# ---------------- ASISTENCIA ----------------
print("\n[ASISTENCIA]")
hoy = dt.date.today().isoformat()
r = perez.post("/asistencia", data={"aula_id": aula1, "fecha": hoy, f"estado_{mateo_m}": "tardanza"}, follow_redirects=True)
chequear("el tutor registra la asistencia de su aula", "guardada" in r.data.decode())
fut = (dt.date.today() + dt.timedelta(days=3)).isoformat()
r = perez.post("/asistencia", data={"aula_id": aula1, "fecha": fut, f"estado_{mateo_m}": "presente"}, follow_redirects=True)
chequear("no permite asistencia de fecha futura", "fecha futura" in r.data.decode())
chequear("docente de área (no tutor) NO ve la asistencia del aula", b"Mateo" not in mendoza.get(f"/asistencia?aula_id={aula1}").data)

# ---------------- JUSTIFICACIONES ----------------
print("\n[JUSTIFICACIONES - 5 días hábiles, Art. 163]")
ana = cliente("a.torres@correo.com", "padre123")   # madre de Mateo
s = get_session()
mateo_est = s.query(Estudiante).filter_by(nombre="Mateo").first().id
viejo = dt.date.today() - dt.timedelta(days=30)
while viejo.weekday() >= 5: viejo -= dt.timedelta(days=1)
rec = dt.date.today() - dt.timedelta(days=1)
while rec.weekday() >= 5: rec -= dt.timedelta(days=1)
a_vieja = Asistencia(estudiante_id=mateo_est, fecha=viejo, estado=EstadoAsistencia.ausente); s.add(a_vieja)
a_rec = s.query(Asistencia).filter_by(estudiante_id=mateo_est, fecha=rec).first()
if a_rec: a_rec.estado = EstadoAsistencia.ausente
else:
    a_rec = Asistencia(estudiante_id=mateo_est, fecha=rec, estado=EstadoAsistencia.ausente); s.add(a_rec)
s.commit(); id_vieja, id_rec = a_vieja.id, a_rec.id; s.close()
t = ana.post(f"/justificaciones/nueva/{id_vieja}", data={"motivo": "Se me olvidó"}, follow_redirects=True).data.decode()
chequear("la madre NO puede justificar una falta de hace 30 días", "5 días hábiles" in t and "pendiente de revisión" not in t)
t = ana.post(f"/justificaciones/nueva/{id_rec}", data={"motivo": "Estuvo con fiebre"}, follow_redirects=True).data.decode()
chequear("la madre SÍ puede justificar una falta reciente", "pendiente de revisión" in t)
chequear("la justificación llega a la bandeja de Dirección", b"fiebre" in adm.get("/justificaciones").data)

# ---------------- SALIDA SEGURA ----------------
print("\n[RECOJO SEGURO - Art. 72 y 76]")
s = get_session()
sofia = s.query(Estudiante).filter_by(nombre="Sofía").first()
rosa = s.query(PersonaAutorizada).filter_by(nombre_completo="Rosa López").first()
padre_sofia, sofia_id, rosa_id = sofia.padres[0].padre_id, sofia.id, rosa.id
s.close()
def salida(est, quien):
    return adm.post("/entrada_salida/registrar", data={"estudiante_id": est, "tipo": "salida", "recogido_por": quien}, follow_redirects=True).data.decode()
chequear("persona autorizada de OTRO niño NO puede recoger a Mateo", "NO registrada" in salida(mateo_est, f"persona:{rosa_id}"))
t = salida(sofia_id, f"persona:{rosa_id}")
chequear("la abuela autorizada SÍ puede recoger a Sofía", "Rosa López" in t and "NO registrada" not in t)
chequear("salida autónoma NO se permite sin autorización escrita", "NO registrada" in salida(sofia_id, "autonoma"))
chequear("salida sin indicar quién recoge NO se permite", "NO registrada" in salida(sofia_id, ""))
chequear("el padre registrado SÍ puede recoger", "NO registrada" not in salida(sofia_id, f"padre:{padre_sofia}"))

# ---------------- PADRES ----------------
print("\n[PADRES - privacidad]")
carlos = cliente("c.lopez@correo.com", "padre123")
r = carlos.get(f"/estudiantes/{sofia_id}")
chequear("el padre ve la ficha de SU hija con informe de progreso", r.status_code == 200 and b"Informe de progreso" in r.data)
chequear("el padre NO ve la ficha de un niño ajeno (403)", carlos.get(f"/estudiantes/{mateo_est}").status_code == 403)
chequear("el padre está bloqueado en pantallas internas", all(carlos.get(x).status_code == 403 for x in
         ["/usuarios", "/estudiantes", "/matriculas", "/calificaciones", "/asistencia", "/aulas"]))
r = carlos.post("/personas_autorizadas/nueva", data={"estudiante_id": mateo_est, "nombre_completo": "Intruso"})
chequear("el padre NO puede autorizar recojo para un niño ajeno", r.status_code == 403)
chequear("el panel del padre muestra a sus hijos con su horario", b"Sof" in carlos.get("/dashboard").data)
r = ana.get(f"/estudiantes/{mateo_est}")
chequear("el boletín de Mateo muestra niveles AD/A/B/C y la conclusión descriptiva", b"logro-AD" in r.data and b"reforzar la escritura" in r.data)

# ---------------- DOCENTE: alcance ----------------
print("\n[DOCENTE - alcance]")
r = maria.get("/estudiantes")
chequear("la tutora de 3 años ve a Emma pero NO a Mateo", b"Emma" in r.data and b"Mateo" not in r.data)
chequear("docente bloqueado en /usuarios y /matriculas", maria.get("/usuarios").status_code == 403 and maria.get("/matriculas").status_code == 403)

# ---------------- USUARIOS ----------------
print("\n[USUARIOS]")
r = adm.post("/usuarios/nuevo", data={"nombre": "Profe Nuevo", "email": "nuevo@mmi.com", "password": "x12345", "role_id": 2, "especialidad": "Arte", "telefono": "900"}, follow_redirects=True)
chequear("crear docente crea también su ficha", "creado correctamente" in r.data.decode())
r = adm.post("/usuarios/nuevo", data={"nombre": "Otro", "email": "nuevo@mmi.com", "password": "x", "role_id": 2}, follow_redirects=True)
chequear("correo repetido muestra mensaje claro (sin error 500)", "Ya existe un usuario" in r.data.decode())
s = get_session(); uid = s.query(Usuario).filter_by(email="m.fernandez@mimundoinfantil.com").first().id; s.close()
r = adm.get(f"/usuarios/eliminar/{uid}", follow_redirects=True)
s = get_session(); sin_tutor = s.query(Aula).join(Grado).filter(Grado.nombre == "3 años").first().tutor_id is None; s.close()
chequear("eliminar a una tutora deja su aula sin tutor (sin romper nada)", r.status_code == 200 and sin_tutor)
chequear("el admin no puede eliminarse a sí mismo", "propia cuenta" in adm.get("/usuarios/eliminar/1", follow_redirects=True).data.decode())

print(f"\n=========== RESULTADO: {ok} correctas, {fail} fallas ===========")
raise SystemExit(1 if fail else 0)
