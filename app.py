from functools import wraps
from base64 import b64decode, b64encode
import uuid

from flask import abort, Flask, jsonify, make_response, request
from flask_cors import CORS

from firebase_admin import credentials, firestore, auth, initialize_app

app = Flask(__name__)
cors = CORS(app)

cred = credentials.Certificate('./firebase.json')
initialize_app(cred)

db = firestore.client()

def base64decode(data):
    if type(data) is str:
        return b64decode(data.encode()).decode('ascii')

    return data

def base64encode(data):
    if type(data) is str:
        return b64encode(data.encode()).decode('ascii')

    return data

def authenticate(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if 'Authorization' in request.headers:
            decoded = auth.verify_id_token(request.headers['Authorization'])

            if decoded:
                return func(uid=decoded['uid'], *args, **kwargs)

        return abort(401)

    return decorated

def get_firestore_tasks(uid):
    data_ref = db.collection(u'data').document(uid)
    docs = data_ref.get().to_dict()['tasks']

    return docs

def get_firestore_decoded_tasks(uid):
    data_ref = db.collection(u'data').document(uid)
    docs = data_ref.get().to_dict()['tasks']

    for doc in docs:
        doc['name'] = base64decode(doc['name'])
        doc['description'] = base64decode(doc['description'])
        doc['section'] = doc['section']
        doc['subtasks'] = [{
            'completed': subtask['completed'],
            'name': base64decode(subtask['name'])
        } for subtask in doc['subtasks']]

    return docs

def set_firestore_tasks(uid, data):
    data_ref = db.collection(u'data').document(uid)
    docs = data_ref.get().to_dict()

    docs['tasks'] = data
    data_ref.set(docs)

def make_task(data):
    if 'name' in data:
        return {
            'id': uuid.uuid1().hex,
            'completed': data.get('completed', False),
            'name': base64encode(data['name']),
            'description': base64encode(data.get('description')),
            'priority': data.get('priority', 4),
            'date': data.get('date'),
            'section': data.get('section'),
            'subtasks': [{
                'completed': subtask.get('completed', False),
                'name': base64encode(subtask['name'])
            } for subtask in data.get('subtasks', [])]
        }

@app.route('/tasks', methods=['GET'])
@authenticate
def get_tasks(uid):
    tasks = get_firestore_decoded_tasks(uid)

    response = make_response(jsonify(tasks))
    response.headers['Access-Control-Allow-Origin'] = '*'

    return response

@app.route('/task', methods=['POST'])
@authenticate
def create_task(uid):
    tasks = get_firestore_tasks(uid)

    data = request.json
    new_task = make_task(data)

    if new_task:
        tasks.append(new_task)

        set_firestore_tasks(uid, tasks)
        return jsonify(new_task), 200

    else:
        return abort(400)

@app.route('/task/<string:task_id>', methods=['PUT'])
@authenticate
def update_task(uid, task_id):
    tasks = get_firestore_tasks(uid)

    data = request.json
    new_task = make_task(data)

    task_index = [task for task in range(len(tasks)) if tasks[task]['id'] == task_id]

    if len(task_index) > 0 and new_task:
        new_task['id'] = tasks[task_index[0]]['id']
        tasks[task_index[0]] = new_task

        set_firestore_tasks(uid, tasks)
        return jsonify(new_task), 200

    else:
        return abort(400)

@app.route('/task/<string:task_id>', methods=['DELETE'])
@authenticate
def delete_task(uid, task_id):
    tasks = get_firestore_tasks(uid)

    new_tasks = list(filter(lambda task: task['id'] != task_id, tasks))

    if len(new_tasks) < len(tasks):
        tasks = new_tasks

        set_firestore_tasks(uid, tasks)
        return jsonify(None), 200

    else:
        return abort(400)

def get_firestore_sections(uid):
    data_ref = db.collection(u'data').document(uid)
    docs = data_ref.get().to_dict()['sections']

    return docs

def get_firestore_decoded_sections(uid):
    data_ref = db.collection(u'data').document(uid)
    docs = data_ref.get().to_dict()['sections']

    for doc in docs:
        doc['name'] = base64decode(doc['name'])

    return docs

def set_firestore_sections(uid, data):
    data_ref = db.collection(u'data').document(uid)
    docs = data_ref.get().to_dict()

    docs['sections'] = data
    data_ref.set(docs)

def make_section(data):
    if 'name' in data:
        return {
            'id': uuid.uuid1().hex,
            'name': base64encode(data['name']),
            'icon': data.get('icon'),
            'color': data.get('color')
        }

@app.route('/sections', methods=['GET'])
@authenticate
def get_sections(uid):
    sections = get_firestore_decoded_sections(uid)

    response = make_response(jsonify(sections))
    response.headers['Access-Control-Allow-Origin'] = '*'

    return response

@app.route('/section', methods=['POST'])
@authenticate
def create_section(uid):
    sections = get_firestore_sections(uid)

    data = request.json
    new_section = make_section(data)

    if new_section:
        sections.append(new_section)

        set_firestore_sections(uid, sections)
        return jsonify(new_section), 200

    else:
        return abort(400)

@app.route('/section/<string:section_id>', methods=['PUT'])
@authenticate
def update_section(uid, section_id):
    sections = get_firestore_sections(uid)

    data = request.json
    new_section = make_section(data)

    section_index = [section for section in range(len(sections)) if sections[section]['id'] == section_id]

    if len(section_index) > 0 and new_section:
        new_section['id'] = sections[section_index[0]]['id']
        sections[section_index[0]] = new_section

        set_firestore_sections(uid, sections)
        return jsonify(new_section), 200

    else:
        return abort(400)

@app.route('/section/<string:section_id>', methods=['DELETE'])
@authenticate
def delete_section(uid, section_id):
    tasks = get_firestore_tasks(uid)
    sections = get_firestore_sections(uid)

    new_sections = list(filter(lambda section: section['id'] != section_id, sections))

    if len(new_sections) < len(sections):
        sections = new_sections
        tasks = list(filter(lambda task: task['section'] != section_id, tasks))

        set_firestore_tasks(uid, tasks)
        set_firestore_sections(uid, sections)

        return jsonify(None), 200

    else:
        return abort(400)
