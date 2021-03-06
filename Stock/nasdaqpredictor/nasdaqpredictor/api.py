import numpy as np
import pandas as pd
from flask import Flask
from flask import jsonify
from datetime import datetime
from werkzeug.routing import BaseConverter, ValidationError
import logging
import nasdaqpredictor
from nasdaqpredictor.model import Model
from nasdaqpredictor.dataloader import DataTransformer, DataLoader

LOGGER = logging.getLogger(__name__)
app = Flask(__name__)

loader = DataLoader('/nasdaq_tickers.csv',
                    datetime(2000, 1, 1),
                    datetime(2017, 1, 1))
transformer = DataTransformer(loader, return_shift_days=-2)
model = Model(transformer,
              dev_date=datetime(2015, 1, 1),
              file_path='models/full_model_2017_11_22_11_07.hdf5')


class DateConverter(BaseConverter):
    regex = r'\d{4}-\d{2}-\d{2}'

    def to_python(self, value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError()

    def to_url(self, value):
        return value.strftime('%Y-%m-%d')


app.url_map.converters['date'] = DateConverter


@app.route('/predict/<ticker>/<date:selected_date>', methods=['GET', 'POST'])
def predict(ticker, selected_date):
    log_msg = 'Predict {}, {}'.format(ticker, selected_date)
    LOGGER.info(log_msg)
    predicted = model.predict_one(ticker, selected_date)
    return jsonify(long_prediction=np.asscalar(predicted[0][0]),
                   short_prediction=np.asscalar(predicted[0][1]))


@app.route('/predict-range/<ticker>/<date:from_date>/<date:to_date>', methods=['GET', 'POST'])
def predict_range(ticker, from_date, to_date):
    log_msg = 'Predict {}, {} - {}'.format(ticker, from_date, to_date)
    LOGGER.info(log_msg)
    daterange = pd.date_range(from_date, to_date)
    dates_predictions = {}
    for single_date in daterange:
        try:
            predicted = model.predict_one(ticker, single_date)
            dates_predictions[single_date.strftime('%Y-%m-%d')] = predicted[0].tolist()
        except Exception as e:
            LOGGER.error(e)
    return jsonify(dates_predictions)


if __name__ == '__main__':
    model.build_model_data()
    model.build_neural_net()
    app.run(port=80, host='0.0.0.0')
