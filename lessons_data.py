# Copyright (C) 2026 Marco Antonio Garcia
#
# Este archivo es parte de este proyecto, software libre bajo la GNU Affero
# General Public License v3 o posterior. Se distribuye SIN NINGUNA GARANTÍA.
# Ver el archivo LICENSE para los términos completos.

# -*- coding: utf-8 -*-
"""
lessons_data.py — Curso completo de Lira (método contrastivo estilo A. Ghio).

Se aprende a HABLAR por EXPLICACIÓN clara (español, sin jerga, comparando con
el español) + traducción paralela. Contenido 100% original; solo la metodología
viene del libro "Inglés Básico".

Estructura de cada lección:
  id, level (beginner|mid|advanced), n (número dentro del nivel),
  block (bloque temático, para el mapa visual), title ("Lección N"),
  desc (una línea: para qué sirve),
  explanation = ["párrafo", ...]   -> la explicación, VA PRIMERO
  pairs       = [[inglés, español], ...]   -> ejemplos (audio 🔊 + ＋ al deck)
  formula     = ["línea resumen", ...]     -> el patrón, en un recuadro
  practice    = [[español, inglés], ...]   -> mini-examen (traduce / revela)

42 lecciones: 14 beginner + 14 mid + 14 advanced.
"""

LESSONS = [
    # ======================================================================
    # BEGINNER (A1–A2) — suficiente para empezar a hablar
    # ======================================================================
    {
        "id": "beg-01", "level": "beginner", "n": 1, "block": "Lo esencial",
        "title": "Lección 1",
        "desc": "Los pronombres personales: quién hace la acción.",
        "explanation": [
            "Antes de armar cualquier frase necesitas saber quién hace la acción. En español muchas veces omitimos el pronombre (decimos «trabajo» sin decir «yo»), pero en inglés casi siempre va delante. Por eso lo primero es aprenderse estos de memoria: son la base de todo lo demás.",
            "Fíjate en un detalle: el inglés usa «it» para cosas y animales, algo que en español no distinguimos. Y «you» sirve igual para «tú», «usted» y «ustedes»: una sola palabra te resuelve el singular y el plural.",
        ],
        "pairs": [
            ["I", "Yo"],
            ["You", "Tú / usted"],
            ["He", "Él"],
            ["She", "Ella"],
            ["It", "Ello (cosas o animales)"],
            ["We", "Nosotros / nosotras"],
            ["They", "Ellos / ellas"],
        ],
        "formula": ["I · you · he · she · it · we · they  =  yo · tú · él · ella · ello · nosotros · ellos"],
        "practice": [
            ["Ella", "She"],
            ["Nosotros", "We"],
            ["Ellos", "They"],
        ],
    },
    {
        "id": "beg-02", "level": "beginner", "n": 2, "block": "Lo esencial",
        "title": "Lección 2",
        "desc": "El verbo to be (am / is / are): soy, estoy, es, está...",
        "explanation": [
            "El verbo más importante del inglés es «to be», y trae una sorpresa cómoda: significa a la vez SER y ESTAR. Los ingleses no separan esas dos ideas como nosotros, así que una sola palabra te sirve para «soy» y para «estoy».",
            "Solo cambia de forma según el pronombre: con «I» se dice «am»; con «he», «she», «it» se dice «is»; y con «you», «we», «they» se dice «are». Apréndete ese trío y ya puedes describir a personas y cosas.",
        ],
        "pairs": [
            ["I am a student.", "Soy un estudiante."],
            ["You are my friend.", "Eres mi amigo."],
            ["He is tall.", "Él es alto."],
            ["She is at home.", "Ella está en casa."],
            ["We are happy.", "Estamos felices / somos felices."],
            ["They are here.", "Ellos están aquí."],
        ],
        "formula": ["I am · he/she/it is · you/we/they are   =   ser / estar"],
        "forms": [
            ["Afirmativo", "He is busy.", "Él está ocupado."],
            ["Negativo", "He isn't busy.", "Él no está ocupado."],
            ["Pregunta", "Is he busy?", "¿Él está ocupado?"],
        ],
        "practice": [
            ["Soy Marco.", "I am Marco."],
            ["Ella está cansada.", "She is tired."],
            ["Nosotros somos amigos.", "We are friends."],
        ],
    },
    {
        "id": "beg-03", "level": "beginner", "n": 3, "block": "Lo esencial",
        "title": "Lección 3",
        "desc": "Los artículos a / an / the y cómo formar el plural.",
        "explanation": [
            "«a» y «an» significan «un/una». Usa «an» cuando la siguiente palabra empieza con sonido de vocal (an apple, an hour) y «a» en los demás casos (a book, a house); es solo para que suene bien.",
            "«the» significa «el, la, los, las» y tiene una gran ventaja: no cambia nunca, ni por género ni por número. Y para el plural, casi siempre basta con agregar una «-s» al final: book → books, car → cars.",
        ],
        "pairs": [
            ["a book", "un libro"],
            ["an apple", "una manzana"],
            ["the house", "la casa"],
            ["two cars", "dos carros"],
            ["the books", "los libros"],
        ],
        "formula": ["a / an = un, una   ·   the = el, la, los, las (no cambia)   ·   plural: + s"],
        "practice": [
            ["una casa", "a house"],
            ["la manzana", "the apple"],
            ["tres perros", "three dogs"],
        ],
    },
    {
        "id": "beg-04", "level": "beginner", "n": 4, "block": "Lo esencial",
        "title": "Lección 4",
        "desc": "El adjetivo: en inglés va ANTES del sustantivo.",
        "explanation": [
            "Aquí hay un cambio clave respecto al español. Nosotros decimos «un libro rojo»: primero la cosa y luego la cualidad. El inglés lo dice al revés, primero la cualidad y luego la cosa, como si dijéramos «un rojo libro»: a red book.",
            "Además, el adjetivo en inglés nunca cambia por género ni por número. «tall» sirve igual para alto, alta, altos y altas. Una sola forma para todo, así que tienes menos que memorizar.",
        ],
        "pairs": [
            ["a red book", "un libro rojo"],
            ["a big house", "una casa grande"],
            ["a good idea", "una buena idea"],
            ["tall men", "hombres altos"],
            ["cold water", "agua fría"],
        ],
        "formula": ["adjetivo + sustantivo   (a RED book = un libro ROJO)   ·   el adjetivo no cambia"],
        "practice": [
            ["una casa nueva", "a new house"],
            ["un carro rápido", "a fast car"],
            ["ojos azules", "blue eyes"],
        ],
    },
    {
        "id": "beg-05", "level": "beginner", "n": 5, "block": "Números y ubicación",
        "title": "Lección 5",
        "desc": "Números, la hora y las fechas.",
        "explanation": [
            "Los números son la base para precios, horas y fechas. Del 1 al 12 hay que aprenderlos de memoria (one, two, three...); del 13 al 19 casi todos llevan «-teen» (thirteen, fourteen) y las decenas llevan «-ty» (twenty, thirty). Cuidado con no confundir «-teen» (13–19) con «-ty» (20, 30): cambian el acento y una letra.",
            "Para la hora se usa «It's» + la hora: It's three o'clock (son las tres en punto). Para meses y fechas, en inglés el mes suele ir primero: July 30th. Con esto ya das precios, horarios y citas.",
        ],
        "pairs": [
            ["It's three o'clock.", "Son las tres en punto."],
            ["It's half past two.", "Son las dos y media."],
            ["I have twenty dollars.", "Tengo veinte dólares."],
            ["My birthday is in July.", "Mi cumpleaños es en julio."],
            ["See you on Monday.", "Nos vemos el lunes."],
        ],
        "formula": [
            "1–12 de memoria   ·   13–19 = + teen   ·   20, 30... = + ty",
            "hora: It's + hora (o'clock / half past / quarter to)",
        ],
        "practice": [
            ["Son las cinco.", "It's five o'clock."],
            ["Tengo trece dólares.", "I have thirteen dollars."],
            ["Nos vemos el viernes.", "See you on Friday."],
        ],
    },
    {
        "id": "beg-06", "level": "beginner", "n": 6, "block": "Números y ubicación",
        "title": "Lección 6",
        "desc": "There is / There are: cómo decir «hay».",
        "explanation": [
            "Para decir que algo existe o que «hay» algo, el inglés usa «there is» (singular) y «there are» (plural). No lo traduzcas literal; simplemente «hay» = there is / there are: There is a book on the table = hay un libro en la mesa.",
            "En preguntas se da la vuelta (Is there...? Are there...?) y en negativo se agrega «not any» o «no»: There isn't any milk = no hay leche. Es una de las estructuras más útiles del día a día.",
        ],
        "pairs": [
            ["There is a book on the table.", "Hay un libro en la mesa."],
            ["There are two cars outside.", "Hay dos carros afuera."],
            ["Is there a bank near here?", "¿Hay un banco cerca de aquí?"],
            ["There aren't any chairs.", "No hay sillas."],
            ["There is a problem.", "Hay un problema."],
        ],
        "formula": [
            "there is (singular) · there are (plural)  =  hay",
            "pregunta: Is / Are there...?   ·   negativo: there isn't / aren't",
        ],
        "practice": [
            ["Hay un gato.", "There is a cat."],
            ["Hay muchas personas.", "There are many people."],
            ["¿Hay agua?", "Is there any water?"],
        ],
    },
    {
        "id": "beg-07", "level": "beginner", "n": 7, "block": "Hablar en presente",
        "title": "Lección 7",
        "desc": "El presente simple: lo que haces siempre o en general.",
        "explanation": [
            "El presente simple sirve para lo que haces normalmente o para verdades generales: «trabajo todos los días», «vivo en México». En inglés es casi igual al verbo tal cual, sin adornos: I work, you live.",
            "El único cuidado está con «he», «she», «it»: a esos se les agrega una «-s» al verbo (he works, she lives, it rains). Es la famosa «-s de la tercera persona»; con los demás pronombres el verbo va sin cambios.",
        ],
        "pairs": [
            ["I work every day.", "Trabajo todos los días."],
            ["You live in Mexico.", "Vives en México."],
            ["He works in a bank.", "Él trabaja en un banco."],
            ["She likes coffee.", "A ella le gusta el café."],
            ["We speak Spanish.", "Hablamos español."],
        ],
        "formula": ["I / you / we / they + verbo   ·   he / she / it + verbo + s"],
        "forms": [
            ["Afirmativo", "She works here.", "Ella trabaja aquí."],
            ["Negativo", "She doesn't work here.", "Ella no trabaja aquí."],
            ["Pregunta", "Does she work here?", "¿Ella trabaja aquí?"],
        ],
        "practice": [
            ["Vivo en la ciudad.", "I live in the city."],
            ["Él habla inglés.", "He speaks English."],
            ["Comemos a las dos.", "We eat at two."],
        ],
    },
    {
        "id": "beg-08", "level": "beginner", "n": 8, "block": "Hablar en presente",
        "title": "Lección 8",
        "desc": "Adverbios de frecuencia: always, usually, sometimes, never.",
        "explanation": [
            "Para decir cada cuánto haces algo se usan palabras como always (siempre), usually (normalmente), sometimes (a veces) y never (nunca). Lo clave es su posición: van ANTES del verbo principal (I always work) pero DESPUÉS del verbo to be (I am always tired).",
            "Ojo con «never»: en inglés ya es negativo por sí solo, así que NO se le agrega «don't» (se dice I never drink, no «I don't never drink»). El doble negativo suena mal en inglés.",
        ],
        "pairs": [
            ["I always drink coffee.", "Siempre tomo café."],
            ["She usually works late.", "Ella normalmente trabaja tarde."],
            ["We sometimes go out.", "A veces salimos."],
            ["He never eats meat.", "Él nunca come carne."],
            ["I am always busy.", "Siempre estoy ocupado."],
        ],
        "formula": [
            "always / usually / sometimes / never  ANTES del verbo",
            "pero DESPUÉS de to be (I am always...)",
        ],
        "practice": [
            ["Siempre estudio.", "I always study."],
            ["Ella nunca llega tarde.", "She never arrives late."],
            ["A veces cocino.", "I sometimes cook."],
        ],
    },
    {
        "id": "beg-09", "level": "beginner", "n": 9, "block": "Hablar en presente",
        "title": "Lección 9",
        "desc": "La terminación -ing y las acciones que pasan ahora.",
        "explanation": [
            "En inglés, para lo que está pasando justo en este momento, se le agrega «-ing» al verbo, igual que nuestro «-ando / -iendo»: work → working (trabajando), eat → eating (comiendo).",
            "Luego se junta con el verbo «to be» (am / is / are) que ya viste, tal como en español juntamos «estar» con el gerundio: I am working = estoy trabajando. La fórmula calca palabra por palabra al español, por eso es tan fácil de sentir.",
        ],
        "pairs": [
            ["I am working.", "Estoy trabajando."],
            ["She is eating an apple.", "Ella está comiendo una manzana."],
            ["They are playing.", "Ellos están jugando."],
            ["We are learning English.", "Estamos aprendiendo inglés."],
            ["He is not sleeping.", "Él no está durmiendo."],
        ],
        "formula": ["am / is / are + verbo-ing   =   estar + -ando / -iendo"],
        "forms": [
            ["Afirmativo", "She is reading.", "Ella está leyendo."],
            ["Negativo", "She isn't reading.", "Ella no está leyendo."],
            ["Pregunta", "Is she reading?", "¿Ella está leyendo?"],
        ],
        "practice": [
            ["Estoy leyendo un libro.", "I am reading a book."],
            ["Ellos están corriendo.", "They are running."],
            ["Ella no está trabajando.", "She is not working."],
        ],
    },
    {
        "id": "beg-10", "level": "beginner", "n": 10, "block": "Hablar en presente",
        "title": "Lección 10",
        "desc": "Pronombres objeto y posesivos: me, him, us; my, mine.",
        "explanation": [
            "Ya viste los pronombres de sujeto (I, you, he...). Cuando reciben la acción cambian de forma: me, you, him, her, it, us, them. «I see him» = lo veo; «call me» = llámame. Van después del verbo o de una preposición (with me, for us).",
            "Para la posesión están los adjetivos my, your, his, her, our, their (mi, tu, su...), que van antes del sustantivo, y los pronombres mine, yours, his, hers, ours, theirs, que se usan cuando no repites la cosa: it's mine = es mío.",
        ],
        "pairs": [
            ["I see him.", "Lo veo."],
            ["Call me tonight.", "Llámame esta noche."],
            ["This is for us.", "Esto es para nosotros."],
            ["It's my book.", "Es mi libro."],
            ["This book is mine.", "Este libro es mío."],
        ],
        "formula": [
            "objeto: me · you · him · her · it · us · them",
            "posesivo: my/your/his... + cosa   ·   mine/yours/hers... (sin cosa)",
        ],
        "practice": [
            ["Llámame.", "Call me."],
            ["Es su carro (de ella).", "It's her car."],
            ["Es mío.", "It's mine."],
        ],
    },
    {
        "id": "beg-11", "level": "beginner", "n": 11, "block": "Pasado, futuro y preguntas",
        "title": "Lección 11",
        "desc": "El futuro: cómo hablar de lo que va a pasar (will / going to).",
        "explanation": [
            "Hay dos formas fáciles de hablar del futuro. La primera es «will» + verbo, que equivale a nuestra terminación «-é / -á»: I will call = llamaré.",
            "La segunda es «going to» + verbo, que es exactamente nuestro «voy a...»: I am going to call = voy a llamar. En el día a día las dos funcionan; «going to» se siente más como un plan y «will» como una decisión del momento, pero no te preocupes por eso al empezar.",
        ],
        "pairs": [
            ["I will call you.", "Te llamaré."],
            ["She will help us.", "Ella nos ayudará."],
            ["I am going to travel.", "Voy a viajar."],
            ["They are going to eat.", "Ellos van a comer."],
            ["It will rain tomorrow.", "Va a llover mañana."],
        ],
        "formula": ["will + verbo = -é / -á     ·     going to + verbo = voy a..."],
        "forms": [
            ["Afirmativo", "She will call.", "Ella llamará."],
            ["Negativo", "She won't call.", "Ella no llamará."],
            ["Pregunta", "Will she call?", "¿Ella llamará?"],
        ],
        "practice": [
            ["Te ayudaré.", "I will help you."],
            ["Vamos a estudiar.", "We are going to study."],
            ["Ella llamará mañana.", "She will call tomorrow."],
        ],
    },
    {
        "id": "beg-12", "level": "beginner", "n": 12, "block": "Pasado, futuro y preguntas",
        "title": "Lección 12",
        "desc": "El pasado simple: cómo contar lo que ya pasó.",
        "explanation": [
            "Para el pasado, a la mayoría de los verbos se les agrega «-ed»: work → worked (trabajé), play → played (jugué). Y una gran comodidad: la forma es la misma para todos los pronombres, no cambia como en español.",
            "Algunos verbos muy comunes son irregulares y hay que aprenderlos de memoria, pero son pocos los de uso diario: go → went (fui), have → had (tuve/tenía), see → saw (vi), eat → ate (comí). Con esos ya te defiendes.",
        ],
        "pairs": [
            ["I worked yesterday.", "Trabajé ayer."],
            ["She played tennis.", "Ella jugó tenis."],
            ["We went to the park.", "Fuimos al parque."],
            ["He had a car.", "Él tenía un carro."],
            ["I saw the movie.", "Vi la película."],
        ],
        "formula": ["verbo + ed (regulares)   ·   went, had, saw, ate... (irregulares, de memoria)"],
        "forms": [
            ["Afirmativo", "They visited us.", "Ellos nos visitaron."],
            ["Negativo", "They didn't visit us.", "Ellos no nos visitaron."],
            ["Pregunta", "Did they visit us?", "¿Ellos nos visitaron?"],
        ],
        "practice": [
            ["Estudié anoche.", "I studied last night."],
            ["Ellos comieron pizza.", "They ate pizza."],
            ["Ella fue a casa.", "She went home."],
        ],
    },
    {
        "id": "beg-13", "level": "beginner", "n": 13, "block": "Pasado, futuro y preguntas",
        "title": "Lección 13",
        "desc": "Cómo decir NO y cómo preguntar.",
        "explanation": [
            "Para negar en presente se usa «don't» antes del verbo (o «doesn't» con he/she/it): I don't work = no trabajo; she doesn't work = ella no trabaja. En pasado siempre es «didn't»: I didn't work = no trabajé. Con el verbo «to be» es más simple todavía: solo agregas «not» (I am not, he is not).",
            "Para preguntar, das la vuelta a la frase. Con «to be» pones el verbo adelante: Are you tired? Con los demás verbos usas «do / does / did» al principio: Do you work? Did you eat? Es un mecanismo fijo, siempre igual.",
        ],
        "pairs": [
            ["I don't work on Sunday.", "No trabajo el domingo."],
            ["She doesn't like tea.", "A ella no le gusta el té."],
            ["I didn't see him.", "No lo vi."],
            ["Are you tired?", "¿Estás cansado?"],
            ["Do you speak English?", "¿Hablas inglés?"],
        ],
        "formula": [
            "negar: don't / doesn't / didn't + verbo   ·   to be: + not",
            "preguntar: Do / Does / Did...?   ·   con to be: Am / Is / Are...?",
        ],
        "practice": [
            ["No hablo francés.", "I don't speak French."],
            ["¿Ellos viven aquí?", "Do they live here?"],
            ["¿Comiste?", "Did you eat?"],
        ],
    },
    {
        "id": "beg-14", "level": "beginner", "n": 14, "block": "Pasado, futuro y preguntas",
        "title": "Lección 14",
        "desc": "Piezas para armar frases: this/that, here/there, some/any.",
        "explanation": [
            "Con estas piezas pequeñas ya puedes armar frases completas del día a día. «this» = este/esta (algo cerca) y «that» = ese/eso (algo lejos); en plural, «these» = estos y «those» = esos.",
            "Suma «here» = aquí y «there» = allá, más «some» (algo, en afirmativo) y «any» (algo/ningún, en preguntas y negaciones). Junta todo esto con las lecciones anteriores y ya tienes lo suficiente para hacerte entender.",
        ],
        "pairs": [
            ["this book", "este libro"],
            ["that house", "esa casa"],
            ["these cars", "estos carros"],
            ["I am here.", "Estoy aquí."],
            ["It is over there.", "Está allá."],
        ],
        "formula": ["this / that = este / ese   ·   these / those = estos / esos   ·   here / there = aquí / allá"],
        "practice": [
            ["esta casa", "this house"],
            ["esos libros", "those books"],
            ["Ella está allá.", "She is there."],
        ],
    },

    # ======================================================================
    # MID (A2–B1)
    # ======================================================================
    {
        "id": "mid-01", "level": "mid", "n": 1, "block": "El perfecto y el pasado",
        "title": "Lección 1",
        "desc": "El presente perfecto: cosas que ya pasaron pero cuentan ahora.",
        "explanation": [
            "El presente perfecto conecta el pasado con el ahora: sirve para experiencias («he viajado a Japón») o para algo terminado hace poco cuyo resultado importa en este momento («he perdido las llaves»). Calca a nuestro «he + participio»: I have traveled = he viajado.",
            "Se arma con «have + participio», y con he/she/it se usa «has». El participio de los regulares es igual al pasado (-ed: worked, lived), pero muchos comunes son irregulares y hay que aprenderlos: go→gone, see→seen, do→done, eat→eaten.",
        ],
        "pairs": [
            ["I have finished my work.", "He terminado mi trabajo."],
            ["She has traveled to Japan.", "Ella ha viajado a Japón."],
            ["We have seen that movie.", "Hemos visto esa película."],
            ["He has lost his keys.", "Él ha perdido sus llaves."],
            ["They have never eaten sushi.", "Ellos nunca han comido sushi."],
        ],
        "formula": ["have / has + participio   =   haber + participio (he/ha + -ado / -ido)"],
        "forms": [
            ["Afirmativo", "I have finished.", "He terminado."],
            ["Negativo", "I haven't finished.", "No he terminado."],
            ["Pregunta", "Have you finished?", "¿Has terminado?"],
        ],
        "practice": [
            ["He comido.", "I have eaten."],
            ["Ella ha terminado.", "She has finished."],
            ["¿Has estado en Londres?", "Have you been to London?"],
        ],
    },
    {
        "id": "mid-02", "level": "mid", "n": 2, "block": "El perfecto y el pasado",
        "title": "Lección 2",
        "desc": "Presente perfecto vs. pasado simple (el gran lío del hispanohablante).",
        "explanation": [
            "Este es el gran lío del hispanohablante. El pasado simple es para algo terminado en un momento definido del pasado: I saw him yesterday (lo vi ayer, tiempo cerrado). El presente perfecto es para algo sin tiempo específico o que sigue conectado al ahora: I have seen that movie (ya la vi, en algún momento).",
            "Regla práctica: si dices CUÁNDO (yesterday, in 2010, last week), usa pasado simple. Si NO dices cuándo, o usas ever / never / already / yet / just, usa presente perfecto: Have you ever been to Paris? / I have just arrived.",
        ],
        "pairs": [
            ["I saw him yesterday.", "Lo vi ayer."],
            ["I have seen that movie.", "He visto esa película."],
            ["She lived in Rome in 2010.", "Ella vivió en Roma en 2010."],
            ["She has lived in many cities.", "Ella ha vivido en muchas ciudades."],
            ["Have you finished yet?", "¿Ya terminaste?"],
        ],
        "formula": [
            "¿dices CUÁNDO? → pasado simple (yesterday, in 2010, last week)",
            "¿sin cuándo / ever, never, just, yet? → presente perfecto",
        ],
        "practice": [
            ["Comí a la una.", "I ate at one."],
            ["¿Alguna vez has volado?", "Have you ever flown?"],
            ["La vi la semana pasada.", "I saw her last week."],
        ],
    },
    {
        "id": "mid-03", "level": "mid", "n": 3, "block": "El perfecto y el pasado",
        "title": "Lección 3",
        "desc": "Algo que empezó antes y todavía sigue (present perfect continuous).",
        "explanation": [
            "Este tiempo describe una acción que empezó en el pasado y todavía sigue, poniendo el énfasis en cuánto ha durado: «he estado trabajando todo el día» (empecé en la mañana y aquí sigo).",
            "Se arma con «have / has + been + verbo-ing», que calca a nuestro «haber + estado + -ando/-iendo». Con he/she/it se usa «has»; con el resto de pronombres, «have». Reconoce la estructura y ya lo tienes.",
        ],
        "pairs": [
            ["I have been working all day.", "He estado trabajando todo el día."],
            ["She has been studying English.", "Ella ha estado estudiando inglés."],
            ["We have been waiting for an hour.", "Hemos estado esperando por una hora."],
            ["They have been living here since 2020.", "Han estado viviendo aquí desde 2020."],
            ["It has been raining.", "Ha estado lloviendo."],
        ],
        "formula": ["have / has + been + verbo-ing   =   haber + estado + -ando / -iendo"],
        "forms": [
            ["Afirmativo", "I have been working.", "He estado trabajando."],
            ["Negativo", "I haven't been working.", "No he estado trabajando."],
            ["Pregunta", "Have you been working?", "¿Has estado trabajando?"],
        ],
        "practice": [
            ["He estado esperando.", "I have been waiting."],
            ["Ella ha estado durmiendo.", "She has been sleeping."],
            ["¿Cuánto tiempo has estado estudiando?", "How long have you been studying?"],
        ],
    },
    {
        "id": "mid-04", "level": "mid", "n": 4, "block": "El perfecto y el pasado",
        "title": "Lección 4",
        "desc": "El pasado continuo: lo que estaba pasando en un momento del pasado.",
        "explanation": [
            "El pasado continuo describe una acción en desarrollo en un momento del pasado: «estaba durmiendo cuando llamaste». Calca a nuestro «estaba + -ando/-iendo»: I was sleeping = estaba durmiendo.",
            "Se arma con el pasado de «to be» (was / were) + verbo-ing. Con I/he/she/it se usa «was»; con you/we/they se usa «were». Se usa mucho junto al pasado simple para lo que interrumpe: I was cooking when she arrived.",
        ],
        "pairs": [
            ["I was sleeping.", "Estaba durmiendo."],
            ["They were playing football.", "Estaban jugando fútbol."],
            ["She was cooking when I arrived.", "Ella estaba cocinando cuando llegué."],
            ["We were waiting for the bus.", "Estábamos esperando el autobús."],
            ["What were you doing?", "¿Qué estabas haciendo?"],
        ],
        "formula": ["was / were + verbo-ing   =   estaba / estaban + -ando / -iendo"],
        "forms": [
            ["Afirmativo", "I was working.", "Estaba trabajando."],
            ["Negativo", "I wasn't working.", "No estaba trabajando."],
            ["Pregunta", "Were you working?", "¿Estabas trabajando?"],
        ],
        "practice": [
            ["Estaba leyendo.", "I was reading."],
            ["Ellos estaban corriendo.", "They were running."],
            ["¿Qué estabas comiendo?", "What were you eating?"],
        ],
    },
    {
        "id": "mid-05", "level": "mid", "n": 5, "block": "El perfecto y el pasado",
        "title": "Lección 5",
        "desc": "El pasado perfecto: el pasado del pasado (había hecho).",
        "explanation": [
            "El pasado perfecto sirve para hablar de algo que pasó ANTES de otro momento del pasado: «cuando llegué, la película ya había empezado». Es, literalmente, el pasado del pasado. Calca a nuestro «había + participio»: I had done = había hecho.",
            "Se arma con «had» (igual para todos los pronombres) + participio. Se usa mucho junto al pasado simple para dejar claro qué ocurrió primero: When I arrived, they had already left.",
        ],
        "pairs": [
            ["The movie had already started.", "La película ya había empezado."],
            ["When I arrived, they had left.", "Cuando llegué, ellos ya se habían ido."],
            ["I had never seen snow before.", "Nunca había visto la nieve antes."],
            ["She had finished her work.", "Ella había terminado su trabajo."],
            ["We had met before.", "Nos habíamos conocido antes."],
        ],
        "formula": ["had + participio   =   había + participio (el pasado del pasado)"],
        "forms": [
            ["Afirmativo", "I had finished.", "Había terminado."],
            ["Negativo", "I hadn't finished.", "No había terminado."],
            ["Pregunta", "Had you finished?", "¿Habías terminado?"],
        ],
        "practice": [
            ["Ya había comido.", "I had already eaten."],
            ["Ellos ya se habían ido.", "They had already left."],
            ["Nunca lo había visto.", "I had never seen it."],
        ],
    },
    {
        "id": "mid-06", "level": "mid", "n": 6, "block": "Modales",
        "title": "Lección 6",
        "desc": "Poder y deber (I): can / could / must / have to.",
        "explanation": [
            "Los modales son palabritas que van antes del verbo, y este siempre queda en su forma base (sin «to»). «can» = poder/saber (I can swim = sé nadar); «could» es su pasado o una versión más cortés (Could you help me? = ¿podrías ayudarme?).",
            "Para la obligación: «must» = deber (fuerte, muchas veces regla propia) y «have to» = tener que (obligación externa). Fíjate que tras el modal el verbo nunca lleva «to»: can go, must go — pero sí «have TO go».",
        ],
        "pairs": [
            ["I can swim.", "Sé nadar / puedo nadar."],
            ["Could you help me?", "¿Podrías ayudarme?"],
            ["You must study.", "Debes estudiar."],
            ["I have to work tomorrow.", "Tengo que trabajar mañana."],
            ["She can't come.", "Ella no puede venir."],
        ],
        "formula": ["can / could / must + verbo (base, sin to)   ·   have to + verbo = tener que"],
        "practice": [
            ["Puedo ayudarte.", "I can help you."],
            ["Tienes que estudiar.", "You have to study."],
            ["¿Podrías esperar?", "Could you wait?"],
        ],
    },
    {
        "id": "mid-07", "level": "mid", "n": 7, "block": "Modales",
        "title": "Lección 7",
        "desc": "Consejo, cortesía y probabilidad (II): should / would / may / might.",
        "explanation": [
            "«should» = debería, para dar consejos: You should rest = deberías descansar. «would» aparece en ofrecimientos y en el condicional: I would like a coffee = me gustaría un café (más educado que «I want»).",
            "Para la probabilidad: «may» y «might» = quizá / puede que. It may rain / It might rain = puede que llueva. «might» suena un poco menos seguro que «may», pero en el día a día son intercambiables.",
        ],
        "pairs": [
            ["You should rest.", "Deberías descansar."],
            ["I would like a coffee.", "Me gustaría un café."],
            ["It may rain later.", "Puede que llueva más tarde."],
            ["She might be at home.", "Quizá ella esté en casa."],
            ["We shouldn't wait.", "No deberíamos esperar."],
        ],
        "formula": ["should = debería   ·   would like = me gustaría   ·   may / might = quizá, puede que"],
        "practice": [
            ["Deberías dormir.", "You should sleep."],
            ["Me gustaría ir.", "I would like to go."],
            ["Puede que él venga.", "He may come."],
        ],
    },
    {
        "id": "mid-08", "level": "mid", "n": 8, "block": "Comparar y cantidades",
        "title": "Lección 8",
        "desc": "Comparar: más grande, el más grande, mejor, peor.",
        "explanation": [
            "Con adjetivos cortos, para comparar se agrega «-er» y luego «than»: tall → taller than = más alto que. Para el superlativo (el más), se usa «the» + «-est»: the tallest = el más alto.",
            "Con adjetivos largos se usa «more» y «the most» en vez de las terminaciones: more expensive, the most expensive. Y hay dos irregulares que debes saber sí o sí: good → better → the best; bad → worse → the worst.",
        ],
        "pairs": [
            ["He is taller than me.", "Él es más alto que yo."],
            ["This is the tallest building.", "Este es el edificio más alto."],
            ["It's more expensive.", "Es más caro."],
            ["She is the best student.", "Ella es la mejor estudiante."],
            ["Today is worse than yesterday.", "Hoy es peor que ayer."],
        ],
        "formula": [
            "cortos: adj + er ... than   ·   the adj + est",
            "largos: more adj   ·   the most adj",
            "irregulares: good/better/best   ·   bad/worse/worst",
        ],
        "practice": [
            ["más rápido que", "faster than"],
            ["el más grande", "the biggest"],
            ["Ella es mejor que yo.", "She is better than me."],
        ],
    },
    {
        "id": "mid-09", "level": "mid", "n": 9, "block": "Comparar y cantidades",
        "title": "Lección 9",
        "desc": "Cantidades: some / any / much / many / a lot of.",
        "explanation": [
            "«some» = algo/algunos, se usa en frases afirmativas (I have some money). «any» = algo/ningún, se usa en preguntas y negaciones (Do you have any money? / I don't have any). Es un cambio automático que al principio cuesta, pero se vuelve natural.",
            "Para «mucho»: «much» va con lo que no se cuenta (much water) y «many» con lo que sí se cuenta en plural (many friends). En afirmativas casi siempre se prefiere «a lot of», que sirve para ambos: a lot of water, a lot of friends.",
        ],
        "pairs": [
            ["I have some money.", "Tengo algo de dinero."],
            ["Do you have any questions?", "¿Tienes alguna pregunta?"],
            ["There isn't any milk.", "No hay leche."],
            ["I don't have much time.", "No tengo mucho tiempo."],
            ["She has a lot of friends.", "Ella tiene muchos amigos."],
        ],
        "formula": [
            "some (afirmativo)   ·   any (pregunta / negación)",
            "much (incontable)   ·   many (contable)   ·   a lot of (ambos)",
        ],
        "practice": [
            ["Tengo algunos libros.", "I have some books."],
            ["¿Hay algún problema?", "Is there any problem?"],
            ["muchos carros", "many cars"],
        ],
    },
    {
        "id": "mid-10", "level": "mid", "n": 10, "block": "Estructuras útiles",
        "title": "Lección 10",
        "desc": "Gerundio vs. infinitivo: want TO go / enjoy GOING.",
        "explanation": [
            "En inglés algunos verbos van seguidos de otro verbo con «to» (infinitivo) y otros con «-ing» (gerundio). No hay una traducción distinta en español, así que hay que aprender qué pide cada uno: I want TO go, pero I enjoy GOING.",
            "Guía rápida: piden infinitivo want, need, would like, decide, hope; piden -ing enjoy, finish, avoid, keep, y todo lo que va tras una preposición (good AT swimming, interested IN learning). Tras «like» y «love» ambas funcionan casi igual.",
        ],
        "pairs": [
            ["I want to go home.", "Quiero ir a casa."],
            ["I enjoy reading.", "Disfruto leer."],
            ["She finished working.", "Ella terminó de trabajar."],
            ["We decided to stay.", "Decidimos quedarnos."],
            ["He's good at swimming.", "Él es bueno nadando."],
        ],
        "formula": [
            "want / need / decide / hope + TO + verbo",
            "enjoy / finish / avoid + verbo-ING   ·   preposición + -ING",
        ],
        "practice": [
            ["Quiero aprender.", "I want to learn."],
            ["Disfruto cocinar.", "I enjoy cooking."],
            ["Terminé de estudiar.", "I finished studying."],
        ],
    },
    {
        "id": "mid-11", "level": "mid", "n": 11, "block": "Estructuras útiles",
        "title": "Lección 11",
        "desc": "Condicionales 1 y 2: condiciones reales e hipotéticas.",
        "explanation": [
            "El primer condicional habla de algo real o probable en el futuro: «si llueve, me quedo en casa». Estructura: If + presente, ... will + verbo. Ojo: en la parte del «if» va presente, no futuro.",
            "El segundo condicional habla de algo hipotético o poco probable: «si tuviera dinero, viajaría». Estructura: If + pasado, ... would + verbo. Es tu «si tuviera... haría». (En inglés cuidado: se prefiere «If I were» en vez de «was».)",
        ],
        "pairs": [
            ["If it rains, I will stay home.", "Si llueve, me quedaré en casa."],
            ["If you study, you will pass.", "Si estudias, aprobarás."],
            ["If I had money, I would travel.", "Si tuviera dinero, viajaría."],
            ["If she were here, she would help.", "Si ella estuviera aquí, ayudaría."],
            ["What would you do?", "¿Qué harías?"],
        ],
        "formula": [
            "1º (real):        If + presente , will + verbo",
            "2º (hipotético):  If + pasado , would + verbo",
        ],
        "practice": [
            ["Si tengo tiempo, te llamo.", "If I have time, I will call you."],
            ["Si fuera rico, viajaría.", "If I were rich, I would travel."],
            ["Si él viniera, hablaríamos.", "If he came, we would talk."],
        ],
    },
    {
        "id": "mid-12", "level": "mid", "n": 12, "block": "Estructuras útiles",
        "title": "Lección 12",
        "desc": "Phrasal verbs comunes: verbo + preposición que cambia el significado.",
        "explanation": [
            "Un phrasal verb es un verbo + una preposición que juntos significan algo distinto. No los traduzcas palabra por palabra; apréndelos como bloques: get up = levantarse, turn on = encender, look for = buscar.",
            "Son de lo más usado en el inglés diario y hacen que suenes natural. Empieza por los más comunes y ve sumando; muchos tienen un equivalente «formal» de una sola palabra, pero el nativo casi siempre usa el phrasal.",
        ],
        "pairs": [
            ["I get up at seven.", "Me levanto a las siete."],
            ["Turn on the light.", "Enciende la luz."],
            ["I'm looking for my keys.", "Estoy buscando mis llaves."],
            ["Please turn off the TV.", "Por favor apaga la tele."],
            ["She gave up smoking.", "Ella dejó de fumar."],
        ],
        "formula": ["verbo + preposición = un solo significado (get up, turn on/off, look for, give up)"],
        "practice": [
            ["Me levanto temprano.", "I get up early."],
            ["Apaga la luz.", "Turn off the light."],
            ["Estoy buscando trabajo.", "I'm looking for a job."],
        ],
    },
    {
        "id": "mid-13", "level": "mid", "n": 13, "block": "Estructuras útiles",
        "title": "Lección 13",
        "desc": "Preposiciones in / on / at y cómo decir de quién es algo.",
        "explanation": [
            "Las tres preposiciones clave: «in» (dentro / meses, años: in May, in a box), «on» (sobre / días: on Monday, on the table) y «at» (en un punto / hora: at 5 o'clock, at home). De lo general a lo específico: in → on → at.",
            "Para la posesión están «my, your, his, her, our, their» y el genitivo con apóstrofo: Marco's book = el libro de Marco. Y los reflexivos «-self/-selves» equivalen a nuestro «me/te/se»: I hurt myself = me lastimé.",
        ],
        "pairs": [
            ["The meeting is on Monday.", "La reunión es el lunes."],
            ["I'll see you at 5 o'clock.", "Te veo a las cinco."],
            ["The keys are in my bag.", "Las llaves están en mi bolsa."],
            ["This is Marco's book.", "Este es el libro de Marco."],
            ["I hurt myself.", "Me lastimé."],
        ],
        "formula": [
            "in (meses / años / dentro)   ·   on (días / sobre)   ·   at (hora / punto)",
            "posesivo 's = de ...   ·   -self / -selves = me / te / se",
        ],
        "practice": [
            ["el lunes", "on Monday"],
            ["a las tres", "at three"],
            ["el carro de ella", "her car"],
        ],
    },
    {
        "id": "mid-14", "level": "mid", "n": 14, "block": "Estructuras útiles",
        "title": "Lección 14",
        "desc": "Question tags y preguntas indirectas: sonar natural y cortés.",
        "explanation": [
            "Las «question tags» son esas coletillas para confirmar, como nuestro «¿verdad?» o «¿no?»: You are tired, aren't you? La regla: si la frase es afirmativa, la coletilla va en negativo, y al revés: She isn't here, is she?",
            "Las preguntas indirectas son más educadas y NO invierten el orden: en vez de «Where is the bank?» dices «Could you tell me where the bank is?» (el verbo va al final, como en una afirmación). Muy útil para sonar cortés.",
        ],
        "pairs": [
            ["You are tired, aren't you?", "Estás cansado, ¿verdad?"],
            ["She isn't here, is she?", "Ella no está aquí, ¿o sí?"],
            ["Could you tell me where the bank is?", "¿Podría decirme dónde está el banco?"],
            ["Do you know what time it is?", "¿Sabes qué hora es?"],
            ["It's cold, isn't it?", "Hace frío, ¿no?"],
        ],
        "formula": [
            "tag: afirmativo → coletilla negativa (..., isn't it?) y viceversa",
            "indirecta: Could you tell me + (sujeto + verbo) — sin invertir",
        ],
        "practice": [
            ["Hace calor, ¿verdad?", "It's hot, isn't it?"],
            ["¿Sabes dónde está?", "Do you know where it is?"],
            ["¿Podría decirme la hora?", "Could you tell me the time?"],
        ],
    },

    # ======================================================================
    # ADVANCED (B2–C1)
    # ======================================================================
    {
        "id": "adv-01", "level": "advanced", "n": 1, "block": "Artículos y hábitos",
        "title": "Lección 1",
        "desc": "Los artículos a fondo: cuándo NO se usa artículo.",
        "explanation": [
            "En básico ya viste a/an/the. Aquí está el matiz que distingue a un avanzado: muchas veces NO se usa artículo. Para hablar de algo en general, en plural o incontable, se va sin «the»: I like music (no «the music»); Dogs are loyal (los perros en general).",
            "Se usa «the» cuando es algo específico o único que ambos ya ubican: the sun, the government, the book I told you about. Regla mental: ¿genérico? sin artículo; ¿esto en concreto que los dos identificamos? the.",
        ],
        "pairs": [
            ["I like music.", "Me gusta la música (en general)."],
            ["Dogs are loyal animals.", "Los perros son animales leales."],
            ["The sun is a star.", "El sol es una estrella."],
            ["She plays the piano.", "Ella toca el piano."],
            ["Life is beautiful.", "La vida es hermosa."],
        ],
        "formula": [
            "genérico / plural / incontable  →  sin artículo",
            "específico / único / ya conocido  →  the",
        ],
        "practice": [
            ["Me gusta el café.", "I like coffee."],
            ["El cielo es azul.", "The sky is blue."],
            ["Los niños son ruidosos.", "Children are noisy."],
        ],
    },
    {
        "id": "adv-02", "level": "advanced", "n": 2, "block": "Artículos y hábitos",
        "title": "Lección 2",
        "desc": "used to / would / be used to: tres formas parecidas que se confunden.",
        "explanation": [
            "Estas tres formas se parecen y por eso se confunden mucho. «used to + verbo» es un hábito del pasado que YA NO haces: I used to smoke = antes fumaba (ya no). «would + verbo» también cuenta hábitos del pasado, pero se usa al narrar recuerdos: when I was a child, we would visit my grandma.",
            "Cuidado con «be / get used to», que es algo distinto aunque se parezca: significa estar (o llegar a estar) acostumbrado a algo, y va seguido de un sustantivo o de un verbo-ing: I am used to the cold; she got used to waking up early.",
        ],
        "pairs": [
            ["I used to smoke.", "Yo solía fumar (ya no)."],
            ["When I was a child, we would visit my grandma.", "De niño, solíamos visitar a mi abuela."],
            ["I am used to the cold.", "Estoy acostumbrado al frío."],
            ["She got used to waking up early.", "Se acostumbró a levantarse temprano."],
            ["He didn't use to like coffee.", "Antes no le gustaba el café."],
        ],
        "formula": [
            "used to + verbo  =  hábito pasado que YA NO pasa",
            "would + verbo  =  hábito pasado repetido (en relatos)",
            "be / get used to + -ing/sustantivo  =  estar / llegar a estar acostumbrado",
        ],
        "practice": [
            ["Yo solía jugar fútbol.", "I used to play soccer."],
            ["Estoy acostumbrado a trabajar de noche.", "I am used to working at night."],
            ["Ella se acostumbró a la ciudad.", "She got used to the city."],
        ],
    },
    {
        "id": "adv-03", "level": "advanced", "n": 3, "block": "Pasiva y causativo",
        "title": "Lección 3",
        "desc": "La voz pasiva: cuando importa la acción, no quién la hace.",
        "explanation": [
            "La voz pasiva se usa cuando no importa (o no se sabe) quién hace la acción, y ponemos el foco en lo que la recibe: «la carta fue escrita». Se forma con el verbo «to be» en el tiempo que toque + el participio: The letter was written.",
            "Si quieres mencionar al autor, se agrega con «by»: The book was written by García Márquez. Calca a nuestro «ser + participio»: is made = es hecho, was built = fue construido, has been done = ha sido hecho.",
        ],
        "pairs": [
            ["The letter was written yesterday.", "La carta fue escrita ayer."],
            ["This car is made in Japan.", "Este carro es hecho en Japón."],
            ["The house was built in 1990.", "La casa fue construida en 1990."],
            ["English is spoken here.", "Aquí se habla inglés."],
            ["The work has been done.", "El trabajo ha sido hecho."],
        ],
        "formula": [
            "be (en el tiempo que toque) + participio   =   ser + participio",
            "autor opcional: ... by + persona",
        ],
        "forms": [
            ["Afirmativo", "The letter was written.", "La carta fue escrita."],
            ["Negativo", "The letter wasn't written.", "La carta no fue escrita."],
            ["Pregunta", "Was the letter written?", "¿La carta fue escrita?"],
        ],
        "practice": [
            ["La comida fue preparada.", "The food was prepared."],
            ["Aquí se vende pan.", "Bread is sold here."],
            ["El puente fue construido.", "The bridge was built."],
        ],
    },
    {
        "id": "adv-04", "level": "advanced", "n": 4, "block": "Pasiva y causativo",
        "title": "Lección 4",
        "desc": "El causativo: hacer que otro haga algo (have / get something done).",
        "explanation": [
            "El causativo se usa cuando NO haces algo tú, sino que haces que otro lo haga por ti: «me corté el pelo» (en la peluquería, no tú con tijeras). En inglés: I had my hair cut. Estructura: have + cosa + participio.",
            "«get» funciona igual y es más informal: I got my car repaired = mandé reparar mi carro. Es un calco de nuestro «mandar / hacer que + participio», y suena muy natural al hablar de servicios.",
        ],
        "pairs": [
            ["I had my hair cut.", "Me corté el pelo (me lo cortaron)."],
            ["I need to get my car repaired.", "Necesito mandar reparar mi carro."],
            ["She had her house painted.", "Ella mandó pintar su casa."],
            ["We had the documents translated.", "Mandamos traducir los documentos."],
            ["Get it done today.", "Haz que lo terminen hoy."],
        ],
        "formula": ["have / get + cosa + participio   =   mandar / hacer que + participio"],
        "practice": [
            ["Mandé arreglar mi teléfono.", "I had my phone fixed."],
            ["Ella se hizo las uñas.", "She had her nails done."],
            ["Necesito cortarme el pelo.", "I need to get my hair cut."],
        ],
    },
    {
        "id": "adv-05", "level": "advanced", "n": 5, "block": "Reportar y condicionar",
        "title": "Lección 5",
        "desc": "Estilo indirecto: contar lo que otro dijo sin repetirlo textual.",
        "explanation": [
            "Para contar lo que alguien dijo, el tiempo verbal suele «retroceder» un paso: el presente pasa a pasado y el pasado a pluscuamperfecto. «I am tired» → He said he was tired. «I will call» → She said she would call.",
            "También cambian los pronombres y las palabras de tiempo/lugar según quién habla (my→his, now→then, today→that day). Para preguntas se usa «asked» + if / palabra interrogativa: He asked if I was ready.",
        ],
        "pairs": [
            ["He said he was tired.", "Dijo que estaba cansado."],
            ["She said she would call.", "Dijo que llamaría."],
            ["They told me they had finished.", "Me dijeron que habían terminado."],
            ["He asked if I was ready.", "Preguntó si yo estaba listo."],
            ["She asked where I lived.", "Preguntó dónde vivía yo."],
        ],
        "formula": [
            "said / told + que...   ·   el tiempo retrocede un paso (present→past, will→would)",
            "preguntas: asked + if / wh-",
        ],
        "practice": [
            ["Dijo que estaba ocupado.", "He said he was busy."],
            ["Dijo que vendría.", "She said she would come."],
            ["Me preguntó si tenía tiempo.", "He asked if I had time."],
        ],
    },
    {
        "id": "adv-06", "level": "advanced", "n": 6, "block": "Reportar y condicionar",
        "title": "Lección 6",
        "desc": "Condicional 3 y mixto: lamentar o imaginar el pasado.",
        "explanation": [
            "El tercer condicional habla de algo que NO pasó en el pasado y su consecuencia imaginaria: «si hubiera estudiado, habría aprobado» (pero no estudié). Estructura: If + had + participio, ... would have + participio.",
            "El condicional mixto cruza tiempos: una condición pasada con consecuencia en el presente («si hubiera ahorrado, ahora sería rico»): If I had saved, I would be rich now. Suena difícil, pero es solo mezclar el 3º con el 2º.",
        ],
        "pairs": [
            ["If I had studied, I would have passed.", "Si hubiera estudiado, habría aprobado."],
            ["If she had known, she would have come.", "Si lo hubiera sabido, habría venido."],
            ["I wouldn't have said that.", "Yo no habría dicho eso."],
            ["If I had saved, I would be rich now.", "Si hubiera ahorrado, ahora sería rico."],
            ["What would you have done?", "¿Qué habrías hecho?"],
        ],
        "formula": [
            "3º:     If + had + participio , would have + participio",
            "mixto:  If + had + participio , would + verbo (ahora)",
        ],
        "practice": [
            ["Si hubiera sabido, habría ayudado.", "If I had known, I would have helped."],
            ["Ella habría venido.", "She would have come."],
            ["¿Qué habrías dicho?", "What would you have said?"],
        ],
    },
    {
        "id": "adv-07", "level": "advanced", "n": 7, "block": "Reportar y condicionar",
        "title": "Lección 7",
        "desc": "wish / if only: expresar deseos y arrepentimientos (ojalá...).",
        "explanation": [
            "«I wish» + pasado expresa un deseo sobre el presente que no es real: I wish I were taller = ojalá fuera más alto (no lo soy). Fíjate que usa pasado aunque hable del presente, igual que nuestro «ojalá + subjuntivo».",
            "«I wish» + had + participio expresa arrepentimiento del pasado: I wish I had studied = ojalá hubiera estudiado. «If only» funciona igual pero con más énfasis: If only I had known.",
        ],
        "pairs": [
            ["I wish I were taller.", "Ojalá fuera más alto."],
            ["I wish I had more time.", "Ojalá tuviera más tiempo."],
            ["I wish I had studied more.", "Ojalá hubiera estudiado más."],
            ["She wishes she could travel.", "Ella desearía poder viajar."],
            ["If only I had known!", "¡Ojalá lo hubiera sabido!"],
        ],
        "formula": [
            "wish + pasado = deseo (presente irreal)",
            "wish + had + participio = arrepentimiento (pasado)",
        ],
        "practice": [
            ["Ojalá fuera rico.", "I wish I were rich."],
            ["Ojalá tuviera un carro.", "I wish I had a car."],
            ["Ojalá hubiera ido.", "I wish I had gone."],
        ],
    },
    {
        "id": "adv-08", "level": "advanced", "n": 8, "block": "Relativas y modales perfectos",
        "title": "Lección 8",
        "desc": "Cláusulas relativas: la persona QUE..., la cosa QUE..., cuyo...",
        "explanation": [
            "Los relativos unen dos ideas en una sola frase y equivalen a nuestro «que / quien / cuyo». «who» = que/quien (personas), «which» = que (cosas), «that» sirve para ambos en frases que definen: The man who called... / The book that I read...",
            "«whose» = cuyo (posesión): the woman whose car... Y ojo con las comas: sin comas la información es esencial (define de quién hablas); con comas es información extra que se podría quitar: My brother, who lives in Paris, is a doctor.",
        ],
        "pairs": [
            ["The man who called is my boss.", "El hombre que llamó es mi jefe."],
            ["The book that I read was great.", "El libro que leí fue genial."],
            ["This is the house which we bought.", "Esta es la casa que compramos."],
            ["The woman whose car broke down.", "La mujer cuyo carro se descompuso."],
            ["My brother, who lives in Paris, is a doctor.", "Mi hermano, que vive en París, es doctor."],
        ],
        "formula": [
            "who (personas) · which (cosas) · that (ambos, define) · whose (cuyo)",
            "con comas = info extra   ·   sin comas = info esencial",
        ],
        "practice": [
            ["el hombre que vive aquí", "the man who lives here"],
            ["el libro que compré", "the book that I bought"],
            ["la mujer cuyo hijo...", "the woman whose son..."],
        ],
    },
    {
        "id": "adv-09", "level": "advanced", "n": 9, "block": "Relativas y modales perfectos",
        "title": "Lección 9",
        "desc": "Modales perfectos: deducir o lamentar el pasado (debí haber...).",
        "explanation": [
            "Los modales perfectos hablan del pasado con un matiz. «should have + participio» = debería haber / debí haber (arrepentimiento): I should have called = debí (haber) llamado.",
            "«must have + participio» = deducción casi segura sobre el pasado: She must have left = seguro (que) ya se fue. «could have + participio» = posibilidad no realizada: I could have won = pude haber ganado (pero no).",
        ],
        "pairs": [
            ["I should have called you.", "Debí (haber) llamado."],
            ["You shouldn't have said that.", "No deberías haber dicho eso."],
            ["She must have forgotten.", "Seguro que lo olvidó."],
            ["He could have won.", "Pudo haber ganado."],
            ["They might have missed the bus.", "Quizá perdieron el autobús."],
        ],
        "formula": [
            "should have + part. = arrepentimiento (debí haber)",
            "must have + part. = deducción segura   ·   could / might have = posibilidad",
        ],
        "practice": [
            ["Debí haber estudiado.", "I should have studied."],
            ["Seguro que se fue.", "She must have left."],
            ["Pude haber ganado.", "I could have won."],
        ],
    },
    {
        "id": "adv-10", "level": "advanced", "n": 10, "block": "Relativas y modales perfectos",
        "title": "Lección 10",
        "desc": "Modales perfectos continuos: should / must / could have been + -ing.",
        "explanation": [
            "Es el paso que faltaba de los modales perfectos: combinan un modal + have + been + verbo-ing, para hablar de una acción EN DESARROLLO en el pasado, con un matiz. «I should have been studying» = debí haber estado estudiando (pero no lo estaba).",
            "Lo usas para deducir o lamentar acciones prolongadas: She must have been sleeping = seguro estaba durmiendo; You could have been hurt = pudiste haberte lastimado. Reconoce el bloque «modal + have been + -ing» y ya lo dominas.",
        ],
        "pairs": [
            ["I should have been studying.", "Debí haber estado estudiando."],
            ["She must have been sleeping.", "Seguro estaba durmiendo."],
            ["You could have been hurt.", "Pudiste haberte lastimado."],
            ["They must have been waiting for hours.", "Seguro llevaban horas esperando."],
            ["He shouldn't have been driving so fast.", "No debió haber estado manejando tan rápido."],
        ],
        "formula": [
            "modal + have + been + verbo-ing",
            "= debí / pude / seguro... haber estado + -ando / -iendo",
        ],
        "practice": [
            ["Debí haber estado trabajando.", "I should have been working."],
            ["Seguro estaba lloviendo.", "It must have been raining."],
            ["Pudiste haber estado durmiendo.", "You could have been sleeping."],
        ],
    },
    {
        "id": "adv-11", "level": "advanced", "n": 11, "block": "El sistema completo",
        "title": "Lección 11",
        "desc": "Futuros avanzados: continuo y perfecto (will be doing / will have done).",
        "explanation": [
            "Más allá de will y going to, hay dos futuros finos. El futuro continuo (will be + -ing) describe algo en desarrollo en un momento futuro: This time tomorrow I will be flying = mañana a esta hora estaré volando.",
            "El futuro perfecto (will have + participio) describe algo que ya estará terminado antes de cierto momento: By 2030, I will have finished my degree = para 2030 ya habré terminado mi carrera. Y su continuo (will have been + -ing) enfatiza la duración.",
        ],
        "pairs": [
            ["This time tomorrow I will be flying.", "Mañana a esta hora estaré volando."],
            ["By 8 pm she will be sleeping.", "A las 8 pm ella estará durmiendo."],
            ["By 2030 I will have finished.", "Para 2030 ya habré terminado."],
            ["They will have arrived by noon.", "Ya habrán llegado para el mediodía."],
            ["I will have been working here for ten years.", "Habré estado trabajando aquí diez años."],
        ],
        "formula": [
            "will be + -ing = estaré + -ando (en un momento futuro)",
            "will have + participio = habré + participio (antes de X)",
        ],
        "practice": [
            ["Mañana estaré trabajando.", "Tomorrow I will be working."],
            ["Para entonces ya habré comido.", "By then I will have eaten."],
            ["Ya habrán terminado.", "They will have finished."],
        ],
    },
    {
        "id": "adv-12", "level": "advanced", "n": 12, "block": "El sistema completo",
        "title": "Lección 12",
        "desc": "El sistema verbal inglés: el mapa que conecta todos los tiempos.",
        "explanation": [
            "Aquí está el «clic» final: todos los tiempos son combinaciones de las MISMAS piezas. Cada verbo tiene tres partes clave — base (work), pasado (worked) y participio (worked / done) — y con los auxiliares be, have y will se arman todos los tiempos.",
            "Fíjate en el patrón: para lo continuo siempre usas be + -ing; para lo perfecto siempre have + participio; para el futuro siempre will. Y se pueden apilar: will have been working = will (futuro) + have been (perfecto) + working (continuo). Cuando ves el sistema, dejas de memorizar reglas sueltas.",
        ],
        "pairs": [
            ["I work / I worked / I have worked", "trabajo / trabajé / he trabajado"],
            ["I am working / I was working", "estoy trabajando / estaba trabajando"],
            ["I have been working", "he estado trabajando"],
            ["I will work / I will be working", "trabajaré / estaré trabajando"],
            ["I will have been working", "habré estado trabajando"],
        ],
        "formula": [
            "continuo: be + -ing   ·   perfecto: have + participio   ·   futuro: will",
            "se apilan: will + have + been + -ing",
        ],
        "practice": [
            ["he comido", "I have eaten"],
            ["estaba comiendo", "I was eating"],
            ["habré estado comiendo", "I will have been eating"],
        ],
    },
    {
        "id": "adv-13", "level": "advanced", "n": 13, "block": "El sistema completo",
        "title": "Lección 13",
        "desc": "Conectores avanzados: however, although, despite, therefore...",
        "explanation": [
            "Para sonar formal y fluido necesitas conectores más allá de «but» y «so». «however» = sin embargo (suele iniciar frase, con coma). «although» / «even though» = aunque (une dos frases). «despite» / «in spite of» = a pesar de (va con sustantivo o -ing, ¡no con una frase completa!).",
            "Para causa y consecuencia: «therefore» = por lo tanto, «because of» = a causa de. Y «whereas» / «while» = mientras que (para contrastar). El error típico es usar «despite» con una frase completa: es despite the rain, no «despite it rained».",
        ],
        "pairs": [
            ["It was expensive; however, I bought it.", "Era caro; sin embargo, lo compré."],
            ["Although it was late, we continued.", "Aunque era tarde, continuamos."],
            ["Despite the rain, we went out.", "A pesar de la lluvia, salimos."],
            ["He was tired; therefore, he rested.", "Estaba cansado; por lo tanto, descansó."],
            ["She likes tea, whereas I prefer coffee.", "A ella le gusta el té, mientras que yo prefiero el café."],
        ],
        "formula": [
            "however = sin embargo   ·   although / even though = aunque (+ frase)",
            "despite / in spite of = a pesar de (+ sustantivo / -ing)   ·   therefore = por lo tanto",
        ],
        "practice": [
            ["Aunque llovía, salimos.", "Although it was raining, we went out."],
            ["A pesar del frío...", "Despite the cold..."],
            ["Sin embargo, lo intenté.", "However, I tried."],
        ],
    },
    {
        "id": "adv-14", "level": "advanced", "n": 14, "block": "El sistema completo",
        "title": "Lección 14",
        "desc": "Inversión, énfasis y colocaciones: recursos para sonar nativo.",
        "explanation": [
            "En registro formal o enfático, ciertas frases invierten el orden (verbo antes del sujeto) al empezar con una palabra negativa: Never have I seen such a thing = nunca he visto algo así; Not only did he win, but... Es un recurso de énfasis, no obligatorio, pero muy elegante.",
            "Y lo que más te hará sonar nativo: las colocaciones, palabras que van juntas por costumbre. No es «do a mistake» sino «make a mistake»; no «take a decision» sino «make a decision»; heavy rain, strong coffee. Apréndelas en bloque, no palabra por palabra.",
        ],
        "pairs": [
            ["Never have I seen such a thing.", "Nunca he visto algo así."],
            ["Not only did he win, but he broke a record.", "No solo ganó, sino que rompió un récord."],
            ["I made a mistake.", "Cometí un error."],
            ["Let's make a decision.", "Tomemos una decisión."],
            ["It was heavy rain.", "Fue una lluvia fuerte."],
        ],
        "formula": [
            "énfasis: Never / Not only + auxiliar + sujeto... (inversión)",
            "colocaciones: make a mistake / decision · heavy rain · strong coffee",
        ],
        "practice": [
            ["Ella cometió un error.", "She made a mistake."],
            ["Tomamos una decisión.", "We made a decision."],
            ["Nunca he visto eso.", "I have never seen that."],
        ],
    },
]
