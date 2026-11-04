from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, session, url_for, flash, g
from flask_bcrypt import Bcrypt
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from db import get_session
from models import (
    Usuario, Rol, Docente, Padre, Estudiante, EstudiantePadre, PersonaAutorizada,
    Grado, Aula, Area, Competencia, AsignacionDocente, Matricula,
    Calificacion, ConclusionDescriptiva, EvaluacionConducta, NivelLogro, Nivel,
    Asistencia, EstadoAsistencia, Justificacion, EstadoJustificacion,
    EntradaSalida, TipoMovimiento, Comunicado, DESCRIPCION_LOGRO,
)

app = Flask(__name__)
app.secret_key = "cambia-esto-por-algo-secreto"
bcrypt = Bcrypt(app)

ADMIN, DOCENTE, PADRE = "Administrador", "Docente", "Padre/Tutor"
LOGROS = ["AD", "A", "B", "C"]
BIMESTRES = [1, 2, 3, 4]


def anio_actual():
    return date.today().year


# ============================================================
# SESIÓN DE BASE DE DATOS: una por petición, se cierra sola
# ============================================================
def get_db():
    if "db" not in g:
        g.db = get_session()
    return g.db


@app.teardown_appcontext
def cerrar_db(exc):
    db = g.pop("db", None)
    if db is not None:
        if exc:
            db.rollback()
        db.close()


@app.context_processor
def variables_globales():
    return {"LOGROS": LOGROS, "DESC_LOGRO": DESCRIPCION_LOGRO, "ANIO": anio_actual()}


# ============================================================
# PERMISOS
# ============================================================
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


def rol_required(*roles_permitidos):
    """Uso: @rol_required('Administrador')  o  @rol_required('Administrador', 'Docente')"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if session.get("rol") not in roles_permitidos:
                return render_template("error.html", codigo=403,
                                       mensaje="No tienes permiso para ver esta página."), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


def denegado(mensaje="No tienes permiso para realizar esta acción."):
    return render_template("error.html", codigo=403, mensaje=mensaje), 403


def _docente_actual(db):
    return db.query(Docente).filter_by(usuario_id=session["usuario_id"]).first()


def _padre_actual(db):
    return db.query(Padre).filter_by(usuario_id=session["usuario_id"]).first()


def _todas_las_aulas(db):
    return db.query(Aula).join(Grado).order_by(Grado.id, Aula.seccion).all()


def _aulas_permitidas(db):
    """Admin: todas. Docente: aulas donde es tutor o tiene un área asignada."""
    if session["rol"] == ADMIN:
        return _todas_las_aulas(db)
    d = _docente_actual(db)
    if not d:
        return []
    ids = {a.id for a in d.aulas_a_cargo} | {x.aula_id for x in d.asignaciones}
    return [a for a in _todas_las_aulas(db) if a.id in ids]


def _aulas_como_tutor(db):
    """Asistencia y conducta las registra el tutor (Art. 161, 135)."""
    if session["rol"] == ADMIN:
        return _todas_las_aulas(db)
    d = _docente_actual(db)
    return [a for a in _todas_las_aulas(db) if d and a.tutor_id == d.id]


def _es_tutor(db, aula):
    if session["rol"] == ADMIN:
        return True
    d = _docente_actual(db)
    return bool(d and aula.tutor_id == d.id)


def _areas_permitidas(db, aula):
    """El tutor califica todas las áreas de su aula; otro docente solo las que tiene asignadas."""
    todas = (db.query(Area).filter_by(nivel=aula.grado.nivel)
             .order_by(Area.es_transversal, Area.id).all())
    if _es_tutor(db, aula):
        return todas
    d = _docente_actual(db)
    ids = {x.area_id for x in d.asignaciones if x.aula_id == aula.id} if d else set()
    return [a for a in todas if a.id in ids]


def _matriculados(db, aula, anio=None):
    return (db.query(Matricula).join(Estudiante)
            .filter(Matricula.aula_id == aula.id,
                    Matricula.anio_lectivo == (anio or anio_actual()),
                    Matricula.estado == "activo")
            .order_by(Estudiante.apellido, Estudiante.nombre).all())


def _hijos_del_padre(db):
    padre = _padre_actual(db)
    if not padre:
        return []
    return [r.estudiante for r in db.query(EstudiantePadre).filter_by(padre_id=padre.id).all()]


def _puede_ver_estudiante(db, est):
    if session["rol"] == ADMIN:
        return True
    if session["rol"] == PADRE:
        return est.id in [h.id for h in _hijos_del_padre(db)]
    if session["rol"] == DOCENTE:
        ids_aulas = [a.id for a in _aulas_permitidas(db)]
        return db.query(Matricula).filter(Matricula.estudiante_id == est.id,
                                          Matricula.aula_id.in_(ids_aulas)).first() is not None if ids_aulas else False
    return False


def dias_habiles_transcurridos(desde, hasta):
    """Cuenta los días hábiles (lunes a viernes) después de 'desde' hasta 'hasta' inclusive."""
    d, n = desde, 0
    while d < hasta:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _desvincular_usuario(db, usuario_id):
    """Antes de borrar un usuario, quita las referencias que otras tablas tienen hacia él."""
    for modelo, columna in ((PersonaAutorizada, "registrado_por_id"), (Comunicado, "emisor_id"),
                            (Calificacion, "registrado_por_id"), (EvaluacionConducta, "registrado_por_id")):
        db.execute(update(modelo).where(getattr(modelo, columna) == usuario_id).values({columna: None}))


# ============================================================
# PÚBLICO: inicio y login
# ============================================================
@app.route("/")
def inicio():
    db = get_db()
    grados = db.query(Grado).order_by(Grado.id).all()
    return render_template("inicio.html",
                           inicial=[g_ for g_ in grados if g_.nivel == Nivel.inicial],
                           primaria=[g_ for g_ in grados if g_.nivel == Nivel.primaria])


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        usuario = db.query(Usuario).filter_by(email=request.form["correo"].strip()).first()
        if usuario and bcrypt.check_password_hash(usuario.password, request.form["clave"]):
            session["usuario_id"] = usuario.id
            session["rol"] = usuario.rol.nombre if usuario.rol else None
            session["nombre"] = usuario.nombre
            return redirect(url_for("dashboard"))
        flash("Correo o clave incorrectos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("inicio"))


# ============================================================
# DASHBOARD según rol
# ============================================================
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    comunicados = db.query(Comunicado).order_by(Comunicado.fecha_publicacion.desc()).limit(4).all()

    if session["rol"] == ADMIN:
        aulas = _todas_las_aulas(db)
        ocupacion = {a.id: len(_matriculados(db, a)) for a in aulas}
        datos = {
            "estudiantes": db.query(Matricula).filter_by(anio_lectivo=anio_actual(), estado="activo").count(),
            "docentes": db.query(Docente).count(),
            "padres": db.query(Padre).count(),
            "asistencias_hoy": db.query(Asistencia).filter_by(fecha=date.today()).count(),
            "pendientes": db.query(Justificacion).filter_by(estado=EstadoJustificacion.pendiente).count(),
        }
        return render_template("dashboard_admin.html", datos=datos, aulas=aulas,
                               ocupacion=ocupacion, comunicados=comunicados)

    if session["rol"] == DOCENTE:
        aulas = _aulas_permitidas(db)
        tutor_ids = {a.id for a in _aulas_como_tutor(db)}
        return render_template("dashboard_docente.html", aulas=aulas, tutor_ids=tutor_ids,
                               comunicados=comunicados)

    hijos = _hijos_del_padre(db)
    return render_template("dashboard_padre.html", hijos=hijos, comunicados=comunicados)


# ============================================================
# USUARIOS (solo Dirección)
# ============================================================
@app.route("/usuarios")
@login_required
@rol_required(ADMIN)
def usuarios():
    return render_template("usuarios.html", usuarios=get_db().query(Usuario).order_by(Usuario.id).all())


@app.route("/usuarios/nuevo", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN)
def nuevo_usuario():
    db = get_db()
    roles = db.query(Rol).all()
    if request.method == "POST":
        try:
            role_id = (request.form["role_id"])
            nuevo = Usuario(nombre=request.form["nombre"].strip(), email=request.form["email"].strip(),
                            password=bcrypt.generate_password_hash(request.form["password"]).decode("utf-8"),
                            role_id=role_id)
            db.add(nuevo)
            db.flush()
            nombre_rol = db.get(Rol, role_id).nombre
            if nombre_rol == DOCENTE:
                db.add(Docente(usuario_id=nuevo.id, especialidad=request.form.get("especialidad"),
                               telefono=request.form.get("telefono")))
            elif nombre_rol == PADRE:
                db.add(Padre(usuario_id=nuevo.id, telefono=request.form.get("telefono", ""),
                             direccion=request.form.get("direccion")))
            db.commit()
            flash("Usuario creado correctamente.", "success")
            return redirect(url_for("usuarios"))
        except IntegrityError:
            db.rollback()
            flash("Ya existe un usuario con ese correo.", "danger")
    return render_template("usuario_form.html", usuario=None, roles=roles)


@app.route("/usuarios/editar/<string:id>", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN)
def editar_usuario(id):
    db = get_db()
    usuario = db.get(Usuario, id)
    if usuario is None:
        return redirect(url_for("usuarios"))
    if request.method == "POST":
        try:
            usuario.nombre = request.form["nombre"].strip()
            usuario.email = request.form["email"].strip()
            if request.form.get("password"):
                usuario.password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
            db.commit()
            flash("Usuario actualizado correctamente.", "success")
            return redirect(url_for("usuarios"))
        except IntegrityError:
            db.rollback()
            flash("Ya existe otro usuario con ese correo.", "danger")
    return render_template("usuario_form.html", usuario=usuario, roles=db.query(Rol).all())


@app.route("/usuarios/eliminar/<string:id>")
@login_required
@rol_required(ADMIN)
def eliminar_usuario(id):
    db = get_db()
    if id == session["usuario_id"]:
        flash("No puedes eliminar tu propia cuenta.", "danger")
        return redirect(url_for("usuarios"))
    usuario = db.get(Usuario, id)
    if usuario:
        if usuario.docente:
            for aula in usuario.docente.aulas_a_cargo:
                aula.tutor_id = None
        _desvincular_usuario(db, id)
        db.delete(usuario)
        db.commit()
        flash("Usuario eliminado correctamente.", "success")
    return redirect(url_for("usuarios"))


# ============================================================
# ESTUDIANTES
# ============================================================
@app.route("/estudiantes")
@login_required
@rol_required(ADMIN, DOCENTE)
def estudiantes():
    db = get_db()
    if session["rol"] == ADMIN:
        lista = db.query(Estudiante).order_by(Estudiante.apellido, Estudiante.nombre).all()
    else:
        lista = []
        for aula in _aulas_permitidas(db):
            lista += [m.estudiante for m in _matriculados(db, aula)]
    matricula_actual = {m.estudiante_id: m for m in db.query(Matricula).filter_by(anio_lectivo=anio_actual()).all()}
    return render_template("estudiantes.html", estudiantes=lista, matricula_actual=matricula_actual)


def _leer_estudiante(est):
    est.nombre = request.form["nombre"].strip()
    est.apellido = request.form["apellido"].strip()
    est.fecha_nacimiento = datetime.strptime(request.form["fecha_nacimiento"], "%Y-%m-%d").date()
    est.dni_documento = request.form.get("dni_documento", "").strip() or None
    est.tiene_nee = bool(request.form.get("tiene_nee"))
    est.salida_autonoma = bool(request.form.get("salida_autonoma"))


@app.route("/estudiantes/nuevo", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN)
def nuevo_estudiante():
    if request.method == "POST":
        db = get_db()
        try:
            est = Estudiante()
            _leer_estudiante(est)
            db.add(est)
            db.commit()
            flash("Estudiante registrado. Ahora puedes matricularlo y vincular a su padre/tutor.", "success")
            return redirect(url_for("detalle_estudiante", id=est.id))
        except IntegrityError:
            db.rollback()
            flash("Ya existe un estudiante con ese DNI.", "danger")
    return render_template("estudiante_form.html", estudiante=None)


@app.route("/estudiantes/editar/<string:id>", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN)
def editar_estudiante(id):
    db = get_db()
    est = db.get(Estudiante, id)
    if est is None:
        return redirect(url_for("estudiantes"))
    if request.method == "POST":
        try:
            _leer_estudiante(est)
            db.commit()
            flash("Estudiante actualizado correctamente.", "success")
            return redirect(url_for("detalle_estudiante", id=id))
        except IntegrityError:
            db.rollback()
            flash("Ya existe otro estudiante con ese DNI.", "danger")
    return render_template("estudiante_form.html", estudiante=est)


@app.route("/estudiantes/eliminar/<string:id>")
@login_required
@rol_required(ADMIN)
def eliminar_estudiante(id):
    db = get_db()
    est = db.get(Estudiante, id)
    if est:
        db.delete(est)
        db.commit()
        flash("Estudiante eliminado correctamente.", "success")
    return redirect(url_for("estudiantes"))


@app.route("/estudiantes/<string:id>")
@login_required
def detalle_estudiante(id):
    """Ficha + boletín de progreso del estudiante."""
    db = get_db()
    est = db.get(Estudiante, id)
    if est is None or not _puede_ver_estudiante(db, est):
        return denegado("No tienes acceso a la ficha de este estudiante.")

    matricula = (db.query(Matricula).filter_by(estudiante_id=id)
                 .order_by(Matricula.anio_lectivo.desc()).first())
    boletin = None
    if matricula:
        nivel = matricula.aula.grado.nivel
        areas = db.query(Area).filter_by(nivel=nivel).order_by(Area.es_transversal, Area.id).all()
        boletin = {
            "areas": areas,
            "logros": {(c.competencia_id, c.bimestre): c.nivel_logro.value for c in matricula.calificaciones},
            "conclusiones": {(c.area_id, c.bimestre): c.texto for c in matricula.conclusiones},
            "conducta": {c.bimestre: c for c in matricula.conductas},
        }

    asistencias = (db.query(Asistencia).filter_by(estudiante_id=id)
                   .order_by(Asistencia.fecha.desc()).all())
    resumen = {e.value: 0 for e in EstadoAsistencia}
    for a in asistencias:
        resumen[a.estado.value] += 1
    return render_template("estudiante_detalle.html", est=est, matricula=matricula, boletin=boletin,
                           asistencias=asistencias[:15], resumen=resumen,
                           edad=est.edad_al_31_marzo(matricula.anio_lectivo) if matricula else None)


@app.route("/estudiantes/<string:id>/asignar_padre", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN)
def asignar_padre(id):
    db = get_db()
    est = db.get(Estudiante, id)
    if request.method == "POST":
        padre_id = (request.form["padre_id"])
        if db.query(EstudiantePadre).filter_by(estudiante_id=id, padre_id=padre_id).first():
            flash("Ese padre/tutor ya estaba vinculado.", "danger")
        else:
            db.add(EstudiantePadre(estudiante_id=id, padre_id=padre_id, parentesco=request.form.get("parentesco")))
            db.commit()
            flash("Padre/tutor vinculado correctamente.", "success")
        return redirect(url_for("detalle_estudiante", id=id))
    return render_template("asignar_padre.html", est=est, padres=db.query(Padre).all())


# ============================================================
# AULAS, ÁREAS Y ASIGNACIÓN DE DOCENTES
# ============================================================
@app.route("/aulas")
@login_required
@rol_required(ADMIN, DOCENTE)
def aulas():
    db = get_db()
    lista = _todas_las_aulas(db) if session["rol"] == ADMIN else _aulas_permitidas(db)
    ocupacion = {a.id: len(_matriculados(db, a)) for a in lista}
    return render_template("aulas.html", aulas=lista, ocupacion=ocupacion)


@app.route("/aulas/<string:id>", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN, DOCENTE)
def detalle_aula(id):
    db = get_db()
    aula = db.get(Aula, id)
    if aula is None or aula not in _aulas_permitidas(db):
        return denegado("No tienes acceso a esta aula.")

    if request.method == "POST":
        if session["rol"] != ADMIN:
            return denegado()
        accion = request.form.get("accion")
        if accion == "tutor":
            aula.tutor_id = (request.form["tutor_id"]) if request.form.get("tutor_id") else None
            aula.capacidad_maxima = (request.form["capacidad_maxima"])
            db.commit()
            flash("Aula actualizada.", "success")
        elif accion == "asignar":
            try:
                db.add(AsignacionDocente(docente_id=(request.form["docente_id"]), aula_id=id,
                                         area_id=(request.form["area_id"])))
                db.commit()
                flash("Docente asignado al área.", "success")
            except IntegrityError:
                db.rollback()
                flash("Esa área ya tiene un docente asignado en esta aula. Quítalo primero para asignar a otro.", "danger")
        return redirect(url_for("detalle_aula", id=id))

    docentes = db.query(Docente).all()
    areas = db.query(Area).filter_by(nivel=aula.grado.nivel, es_transversal=False).order_by(Area.id).all()
    return render_template("aula_detalle.html", aula=aula, matriculados=_matriculados(db, aula),
                           docentes=docentes, areas=areas)


@app.route("/aulas/<string:id>/quitar_asignacion/<string:asignacion_id>")
@login_required
@rol_required(ADMIN)
def quitar_asignacion(id, asignacion_id):
    db = get_db()
    a = db.get(AsignacionDocente, asignacion_id)
    if a:
        db.delete(a)
        db.commit()
        flash("Asignación eliminada.", "success")
    return redirect(url_for("detalle_aula", id=id))


@app.route("/areas")
@login_required
@rol_required(ADMIN, DOCENTE)
def areas():
    db = get_db()
    plan = {}
    for nivel in (Nivel.inicial, Nivel.primaria):
        plan[nivel.value] = db.query(Area).filter_by(nivel=nivel).order_by(Area.es_transversal, Area.id).all()
    return render_template("areas.html", plan=plan)


# ============================================================
# MATRÍCULAS (con las reglas del reglamento: edad y capacidad)
# ============================================================
@app.route("/matriculas")
@login_required
@rol_required(ADMIN)
def matriculas():
    db = get_db()
    anio = (request.args.get("anio", anio_actual()))
    lista = (db.query(Matricula).join(Estudiante).filter(Matricula.anio_lectivo == anio)
             .order_by(Estudiante.apellido).all())
    return render_template("matriculas.html", matriculas=lista, anio_sel=anio)


@app.route("/matriculas/nueva", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN)
def nueva_matricula():
    db = get_db()
    if request.method == "POST":
        est = db.get(Estudiante, (request.form["estudiante_id"]))
        aula = db.get(Aula, (request.form["aula_id"]))
        anio = (request.form["anio_lectivo"])
        forzar = bool(request.form.get("forzar"))
        grado = aula.grado
        edad = est.edad_al_31_marzo (int(anio))

        errores = []
        if db.query(Matricula).filter_by(estudiante_id=est.id, anio_lectivo=anio).first():
            errores.append(f"{est.nombre_completo} ya tiene una matrícula en {anio}.")
        if len(_matriculados(db, aula, anio)) >= aula.capacidad_maxima:
            errores.append(f"El aula {aula.nombre} ya alcanzó su capacidad máxima ({aula.capacidad_maxima}) - Art. 82.")
        if not forzar and not (grado.edad_normativa <= edad <= grado.edad_maxima):
            errores.append(
                f"Edad al 31 de marzo de {anio}: {edad} años. Para {grado.nombre} el reglamento exige entre "
                f"{grado.edad_normativa} y {grado.edad_maxima} años (Anexo 2). "
                "Si Dirección autoriza una excepción, marca la casilla correspondiente.")
        if errores:
            for e in errores:
                flash(e, "danger")
        else:
            db.add(Matricula(estudiante_id=est.id, aula_id=aula.id, anio_lectivo=anio, estado="activo"))
            db.commit()
            flash("Matrícula registrada correctamente.", "success")
            return redirect(url_for("matriculas", anio=anio))

    return render_template("matricula_form.html", estudiantes=db.query(Estudiante).order_by(Estudiante.apellido).all(),
                           aulas=_todas_las_aulas(db), anio_default=anio_actual())


@app.route("/matriculas/editar/<string:id>", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN)
def editar_matricula(id):
    """Cambiar el estado (activo/retirado) o trasladar de sección dentro del mismo grado."""
    db = get_db()
    m = db.get(Matricula, id)
    if m is None:
        return redirect(url_for("matriculas"))
    mismo_grado = [a for a in _todas_las_aulas(db) if a.grado_id == m.aula.grado_id]

    if request.method == "POST":
        nueva_aula = db.get(Aula, request.form["aula_id"])
        nuevo_estado = request.form["estado"]
        if nueva_aula is None or nueva_aula.grado_id != m.aula.grado_id or nuevo_estado not in ("activo", "retirado"):
            flash("Datos no válidos.", "danger")
            return redirect(url_for("editar_matricula", id=id))
        # Si queda activo en un aula distinta (o se reactiva), debe haber cupo
        if nuevo_estado == "activo" and (nueva_aula.id != m.aula_id or m.estado != "activo"):
            ocupados = [x for x in _matriculados(db, nueva_aula, m.anio_lectivo) if x.id != m.id]
            if len(ocupados) >= nueva_aula.capacidad_maxima:
                flash(f"El aula {nueva_aula.nombre} ya alcanzó su capacidad máxima ({nueva_aula.capacidad_maxima}).", "danger")
                return redirect(url_for("editar_matricula", id=id))
        m.aula_id, m.estado = nueva_aula.id, nuevo_estado
        db.commit()
        flash("Matrícula actualizada correctamente.", "success")
        return redirect(url_for("matriculas", anio=m.anio_lectivo))
    return render_template("matricula_editar.html", m=m, aulas=mismo_grado)


@app.route("/matriculas/eliminar/<string:id>")
@login_required
@rol_required(ADMIN)
def eliminar_matricula(id):
    db = get_db()
    m = db.get(Matricula, id)
    if m:
        anio = m.anio_lectivo
        db.delete(m)
        db.commit()
        flash("Matrícula eliminada correctamente.", "success")
        return redirect(url_for("matriculas", anio=anio))
    return redirect(url_for("matriculas"))


# ============================================================
# CALIFICACIONES: escala literal AD/A/B/C por competencia y bimestre
# ============================================================
@app.route("/calificaciones", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN, DOCENTE)
def calificaciones():
    db = get_db()
    aulas_ok = _aulas_permitidas(db)
    aula_id = request.values.get("aula_id", type=int)
    area_id = request.values.get("area_id", type=int)
    bimestre = request.values.get("bimestre", 1, type=int)

    aula = next((a for a in aulas_ok if a.id == aula_id), None)
    areas_ok = _areas_permitidas(db, aula) if aula else []
    area = next((a for a in areas_ok if a.id == area_id), None)
    if bimestre not in BIMESTRES:
        bimestre = 1

    matriculados, logros, conclusiones = [], {}, {}
    if aula and area:
        matriculados = _matriculados(db, aula)
        ids = [m.id for m in matriculados]
        if request.method == "POST":
            sin_conclusion = []
            # Art. 133: inicial -> conclusión si hay A, B o C; primaria -> si hay B o C
            exigen = {"A", "B", "C"} if aula.grado.nivel == Nivel.inicial else {"B", "C"}
            for m in matriculados:
                valores = []
                for comp in area.competencias:
                    valor = request.form.get(f"n_{m.id}_{comp.id}", "")
                    fila = db.query(Calificacion).filter_by(matricula_id=m.id, competencia_id=comp.id,
                                                            bimestre=bimestre).first()
                    if valor in LOGROS:
                        valores.append(valor)
                        if fila:
                            fila.nivel_logro = NivelLogro(valor)
                            fila.registrado_por_id = session["usuario_id"]
                        else:
                            db.add(Calificacion(matricula_id=m.id, competencia_id=comp.id, bimestre=bimestre,
                                                nivel_logro=NivelLogro(valor), registrado_por_id=session["usuario_id"]))
                    elif fila:
                        db.delete(fila)
                texto = request.form.get(f"c_{m.id}", "").strip()
                concl = db.query(ConclusionDescriptiva).filter_by(matricula_id=m.id, area_id=area.id,
                                                                  bimestre=bimestre).first()
                if texto:
                    if concl:
                        concl.texto = texto
                    else:
                        db.add(ConclusionDescriptiva(matricula_id=m.id, area_id=area.id, bimestre=bimestre, texto=texto))
                elif concl:
                    db.delete(concl)
                if not texto and exigen & set(valores):
                    sin_conclusion.append(m.estudiante.nombre_completo)
            db.commit()
            flash(f"Calificaciones de {area.nombre} - Bimestre {bimestre} guardadas.", "success")
            if sin_conclusion:
                flash("Según el Art. 133 del reglamento falta la conclusión descriptiva de: "
                      + ", ".join(sin_conclusion) + ".", "warning")
            return redirect(url_for("calificaciones", aula_id=aula.id, area_id=area.id, bimestre=bimestre))

        for c in db.query(Calificacion).filter(Calificacion.matricula_id.in_(ids), Calificacion.bimestre == bimestre):
            logros[(c.matricula_id, c.competencia_id)] = c.nivel_logro.value
        for c in db.query(ConclusionDescriptiva).filter(ConclusionDescriptiva.matricula_id.in_(ids),
                                                        ConclusionDescriptiva.area_id == area.id,
                                                        ConclusionDescriptiva.bimestre == bimestre):
            conclusiones[c.matricula_id] = c.texto

    return render_template("calificaciones.html", aulas=aulas_ok, aula=aula, areas=areas_ok, area=area,
                           bimestre=bimestre, matriculados=matriculados, logros=logros, conclusiones=conclusiones)


# ============================================================
# CONDUCTA (la evalúa el tutor)
# ============================================================
@app.route("/conducta", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN, DOCENTE)
def conducta():
    db = get_db()
    aulas_ok = _aulas_como_tutor(db)
    aula_id = request.values.get("aula_id", type=int)
    bimestre = request.values.get("bimestre", 1, type=int)
    aula = next((a for a in aulas_ok if a.id == aula_id), None)
    if bimestre not in BIMESTRES:
        bimestre = 1

    matriculados, actuales = [], {}
    if aula:
        matriculados = _matriculados(db, aula)
        if request.method == "POST":
            for m in matriculados:
                vals = [request.form.get(f"{campo}_{m.id}", "") for campo in ("comp", "punt", "pres")]
                fila = db.query(EvaluacionConducta).filter_by(matricula_id=m.id, bimestre=bimestre).first()
                if all(v in LOGROS for v in vals):
                    datos = dict(comportamiento=NivelLogro(vals[0]), puntualidad=NivelLogro(vals[1]),
                                 presentacion_personal=NivelLogro(vals[2]), registrado_por_id=session["usuario_id"])
                    if fila:
                        for k, v in datos.items():
                            setattr(fila, k, v)
                    else:
                        db.add(EvaluacionConducta(matricula_id=m.id, bimestre=bimestre, **datos))
            db.commit()
            flash(f"Conducta del Bimestre {bimestre} guardada.", "success")
            return redirect(url_for("conducta", aula_id=aula.id, bimestre=bimestre))
        actuales = {c.matricula_id: c for c in db.query(EvaluacionConducta).filter(
            EvaluacionConducta.matricula_id.in_([m.id for m in matriculados]),
            EvaluacionConducta.bimestre == bimestre)}
    return render_template("conducta.html", aulas=aulas_ok, aula=aula, bimestre=bimestre,
                           matriculados=matriculados, actuales=actuales)


# ============================================================
# ASISTENCIA (la registra el tutor del aula)
# ============================================================
@app.route("/asistencia", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN, DOCENTE)
def asistencia():
    db = get_db()
    aulas_ok = _aulas_como_tutor(db)
    aula_id = request.values.get("aula_id", type=int)
    aula = next((a for a in aulas_ok if a.id == aula_id), None)
    if aula is None and len(aulas_ok) == 1:
        aula = aulas_ok[0]
    try:
        fecha_sel = datetime.strptime(request.values.get("fecha") or date.today().isoformat(), "%Y-%m-%d").date()
    except ValueError:
        fecha_sel = date.today()

    matriculados, registradas = [], {}
    if aula:
        matriculados = _matriculados(db, aula)
        if request.method == "POST":
            if fecha_sel > date.today():
                flash("No se puede registrar asistencia de una fecha futura.", "danger")
                return redirect(url_for("asistencia", aula_id=aula.id))
            for m in matriculados:
                estado = request.form.get(f"estado_{m.id}")
                if estado not in [e.value for e in EstadoAsistencia]:
                    continue
                fila = db.query(Asistencia).filter_by(estudiante_id=m.estudiante_id, fecha=fecha_sel).first()
                if fila:
                    fila.estado = EstadoAsistencia(estado)
                else:
                    db.add(Asistencia(estudiante_id=m.estudiante_id, fecha=fecha_sel, estado=EstadoAsistencia(estado)))
            db.commit()
            flash(f"Asistencia del {fecha_sel.strftime('%d/%m/%Y')} guardada para {aula.nombre}.", "success")
            return redirect(url_for("asistencia", aula_id=aula.id, fecha=fecha_sel.isoformat()))
        registradas = {a.estudiante_id: a.estado.value for a in db.query(Asistencia).filter(
            Asistencia.fecha == fecha_sel,
            Asistencia.estudiante_id.in_([m.estudiante_id for m in matriculados]))}
    return render_template("asistencia.html", aulas=aulas_ok, aula=aula, fecha_sel=fecha_sel,
                           matriculados=matriculados, registradas=registradas, estados=EstadoAsistencia,
                           hoy=date.today())


# ============================================================
# JUSTIFICACIONES (Art. 163: plazo de 5 días hábiles)
# ============================================================
@app.route("/justificaciones")
@login_required
@rol_required(ADMIN, DOCENTE)
def justificaciones():
    db = get_db()
    lista = db.query(Justificacion).order_by(Justificacion.fecha_solicitud.desc()).all()
    if session["rol"] == DOCENTE:
        ids_est = {m.estudiante_id for a in _aulas_permitidas(db) for m in _matriculados(db, a)}
        lista = [j for j in lista if j.asistencia.estudiante_id in ids_est]
    return render_template("justificaciones.html", justificaciones=lista)


@app.route("/justificaciones/nueva/<string:asistencia_id>", methods=["GET", "POST"])
@login_required
def nueva_justificacion(asistencia_id):
    db = get_db()
    asis = db.get(Asistencia, asistencia_id)
    if asis is None or not _puede_ver_estudiante(db, asis.estudiante):
        return denegado()
    transcurridos = dias_habiles_transcurridos(asis.fecha, date.today())
    fuera_de_plazo = transcurridos > 5 and session["rol"] == PADRE

    if request.method == "POST":
        if fuera_de_plazo:
            flash("Pasaron más de 5 días hábiles: según el Art. 163 la justificación debe hacerse en ese plazo. "
                  "Comunícate con Dirección.", "danger")
        else:
            db.add(Justificacion(asistencia_id=asistencia_id, motivo=request.form["motivo"].strip()))
            db.commit()
            flash("Justificación enviada, quedó pendiente de revisión.", "success")
            return redirect(url_for("detalle_estudiante", id=asis.estudiante_id))
    return render_template("justificacion_form.html", asis=asis, transcurridos=transcurridos,
                           fuera_de_plazo=fuera_de_plazo)


@app.route("/justificaciones/<string:id>/<accion>")
@login_required
@rol_required(ADMIN, DOCENTE)
def resolver_justificacion(id, accion):
    if accion not in ("aprobar", "rechazar"):
        return denegado("Acción no válida.")
    db = get_db()
    j = db.get(Justificacion, id)
    if j:
        if accion == "aprobar":
            j.estado = EstadoJustificacion.aprobado
            j.asistencia.estado = EstadoAsistencia.justificado
        else:
            j.estado = EstadoJustificacion.rechazado
        db.commit()
        flash("Justificación " + ("aprobada" if accion == "aprobar" else "rechazada") + ".", "success")
    return redirect(url_for("justificaciones"))


# ============================================================
# ENTRADA / SALIDA (control de recojo: solo personas autorizadas)
# ============================================================
@app.route("/entrada_salida")
@login_required
@rol_required(ADMIN, DOCENTE)
def entrada_salida():
    db = get_db()
    ids_est = None
    if session["rol"] == DOCENTE:
        ids_est = {m.estudiante_id for a in _aulas_permitidas(db) for m in _matriculados(db, a)}
    consulta = db.query(EntradaSalida).order_by(EntradaSalida.fecha_hora.desc())
    movimientos = [m for m in consulta.limit(80).all() if ids_est is None or m.estudiante_id in ids_est]
    estudiantes_lista = [db.get(Estudiante, i) for i in ids_est] if ids_est is not None else \
        db.query(Estudiante).order_by(Estudiante.apellido).all()

    opciones = {}
    for est in estudiantes_lista:
        ops = [{"v": f"padre:{r.padre_id}", "t": f"{r.padre.usuario.nombre} ({r.parentesco or 'Padre/Tutor'})"}
               for r in est.padres if r.padre and r.padre.usuario]
        ops += [{"v": f"persona:{p.id}", "t": f"{p.nombre_completo} ({p.parentesco_o_relacion or 'Autorizado'})"}
                for p in est.personas_autorizadas]
        if est.salida_autonoma:
            ops.append({"v": "autonoma", "t": "Salida autónoma (autorizada por escrito)"})
        opciones[est.id] = ops
    return render_template("entrada_salida.html", movimientos=movimientos, estudiantes=estudiantes_lista,
                           opciones=opciones)


@app.route("/entrada_salida/registrar", methods=["POST"])
@login_required
@rol_required(ADMIN, DOCENTE)
def registrar_movimiento():
    db = get_db()
    est = db.get(Estudiante, (request.form["estudiante_id"]))
    tipo = request.form["tipo"]
    if est is None or not _puede_ver_estudiante(db, est):
        return denegado()

    if tipo == "entrada":
        db.add(EntradaSalida(estudiante_id=est.id, tipo=TipoMovimiento.entrada, detalle="Ingreso"))
        db.commit()
        flash(f"Ingreso de {est.nombre_completo} registrado.", "success")
        return redirect(url_for("entrada_salida"))

    # Salida: SOLO puede salir con un padre/tutor, una persona autorizada, o salida autónoma autorizada
    quien = request.form.get("recogido_por", "")
    persona_id, detalle = None, None
    if quien.startswith("padre:"):
        r = db.query(EstudiantePadre).filter_by(estudiante_id=est.id, padre_id=int(quien.split(":")[1])).first()
        if r:
            detalle = f"Retirado por {r.padre.usuario.nombre} ({r.parentesco or 'Padre/Tutor'})"
    elif quien.startswith("persona:"):
        p = db.get(PersonaAutorizada, int(quien.split(":")[1]))
        if p and p.estudiante_id == est.id:
            persona_id = p.id
            detalle = f"Retirado por {p.nombre_completo} ({p.parentesco_o_relacion or 'Autorizado'})"
    elif quien == "autonoma" and est.salida_autonoma:
        detalle = "Salida autónoma autorizada por el padre (Art. 76)"

    if detalle is None:
        flash("Salida NO registrada: la persona que recoge debe ser un padre/tutor o una persona autorizada de este estudiante.", "danger")
        return redirect(url_for("entrada_salida"))
    db.add(EntradaSalida(estudiante_id=est.id, tipo=TipoMovimiento.salida, persona_autorizada_id=persona_id, detalle=detalle))
    db.commit()
    flash(f"Salida de {est.nombre_completo} registrada. {detalle}.", "success")
    return redirect(url_for("entrada_salida"))


# ============================================================
# COMUNICADOS
# ============================================================
@app.route("/comunicados")
@login_required
def comunicados():
    lista = get_db().query(Comunicado).order_by(Comunicado.fecha_publicacion.desc()).all()
    return render_template("comunicados.html", comunicados=lista)


@app.route("/comunicados/nuevo", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN, DOCENTE)
def nuevo_comunicado():
    if request.method == "POST":
        db = get_db()
        db.add(Comunicado(titulo=request.form["titulo"].strip(), contenido=request.form["contenido"].strip(),
                          emisor_id=session["usuario_id"]))
        db.commit()
        flash("Comunicado publicado correctamente.", "success")
        return redirect(url_for("comunicados"))
    return render_template("comunicado_form.html")


@app.route("/comunicados/eliminar/<string:id>")
@login_required
@rol_required(ADMIN)
def eliminar_comunicado(id):
    db = get_db()
    c = db.get(Comunicado, id)
    if c:
        db.delete(c)
        db.commit()
        flash("Comunicado eliminado correctamente.", "success")
    return redirect(url_for("comunicados"))


# ============================================================
# PERSONAS AUTORIZADAS (seguridad escolar - Art. 72)
# ============================================================
@app.route("/personas_autorizadas")
@login_required
@rol_required(ADMIN, PADRE)
def personas_autorizadas():
    db = get_db()
    if session["rol"] == ADMIN:
        lista = db.query(PersonaAutorizada).all()
    else:
        ids = [h.id for h in _hijos_del_padre(db)]
        lista = db.query(PersonaAutorizada).filter(PersonaAutorizada.estudiante_id.in_(ids)).all() if ids else []
    return render_template("personas_autorizadas.html", personas=lista)


@app.route("/personas_autorizadas/nueva", methods=["GET", "POST"])
@login_required
@rol_required(ADMIN, PADRE)
def nueva_persona_autorizada():
    db = get_db()
    hijos = _hijos_del_padre(db) if session["rol"] == PADRE else db.query(Estudiante).order_by(Estudiante.apellido).all()
    if request.method == "POST":
        estudiante_id = (request.form["estudiante_id"])
        if estudiante_id not in [h.id for h in hijos]:
            return denegado("Ese estudiante no es tu hijo/a registrado.")
        db.add(PersonaAutorizada(estudiante_id=estudiante_id, nombre_completo=request.form["nombre_completo"].strip(),
                                 dni=request.form.get("dni"), parentesco_o_relacion=request.form.get("parentesco_o_relacion"),
                                 telefono=request.form.get("telefono"), registrado_por_id=session["usuario_id"]))
        db.commit()
        flash("Persona autorizada registrada correctamente.", "success")
        return redirect(url_for("personas_autorizadas"))
    return render_template("persona_autorizada_form.html", hijos=hijos)


@app.route("/personas_autorizadas/eliminar/<string:id>")
@login_required
@rol_required(ADMIN, PADRE)
def eliminar_persona_autorizada(id):
    db = get_db()
    p = db.get(PersonaAutorizada, id)
    if p:
        if session["rol"] == PADRE and p.estudiante_id not in [h.id for h in _hijos_del_padre(db)]:
            return denegado()
        db.delete(p)
        db.commit()
        flash("Persona autorizada eliminada correctamente.", "success")
    return redirect(url_for("personas_autorizadas"))


if __name__ == "__main__":
    app.run(debug=True)
