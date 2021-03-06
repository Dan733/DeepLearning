from collections import deque

import numpy as np
import logging
import random

from keras.models import Sequential
from keras.layers.core import Dense, Dropout, Activation, Flatten
from keras.optimizers import Adam
from keras.losses import mean_squared_error

from keras.layers import Conv1D, MaxPooling1D

LOGGER = logging.getLogger(__name__)


class Agent:
    def __init__(self,
                 input_shape,
                 action_size,
                 epochs=0,
                 layer_decrease_multiplier=0.8,
                 min_epsilon=0.05,
                 gamma=0.1,
                 replay_buffer=32,
                 memory_queue_length=64):
        self.input_shape = input_shape
        self.action_size = action_size
        self.epochs = epochs

        self.layer_decrease_multiplier = layer_decrease_multiplier
        self.min_epsilon = min_epsilon
        self.gamma = gamma  # how much should we look into the future predicitons

        self.epsilon = 1
        self.replay_buffer = replay_buffer
        self.memory_queue_length = memory_queue_length
        self.reset_memory()

        self._build_model()

    def reset_memory(self):
        self.replay_index = 0
        self.memory = {}
        for i in range(self.action_size):
            self.memory[i] = deque(maxlen=self.memory_queue_length)

    def _build_model(self):
        first_layer_size = int(self.input_shape[0] *
                               self.layer_decrease_multiplier)
        second_layer_size = int(first_layer_size * self.layer_decrease_multiplier)
        third_layer_size = int(second_layer_size * self.layer_decrease_multiplier)

        model = Sequential()

        # CNN layers
        model.add(Conv1D(input_shape=self.input_shape,
                         filters=64,
                         kernel_size=4,
                         padding='same',
                         activation='relu'))
        model.add(Conv1D(filters=64,
                         kernel_size=4,
                         padding='same',
                         activation='relu'))
        model.add(MaxPooling1D(pool_size=4))
        model.add(Conv1D(filters=128,
                         kernel_size=4,
                         padding='same',
                         activation='relu'))
        model.add(Conv1D(filters=128,
                         kernel_size=4,
                         padding='same',
                         activation='relu'))
        model.add(MaxPooling1D(pool_size=4))
        model.add(Flatten())

        model.add(Dense(first_layer_size))
        model.add(Activation('relu'))
        model.add(Dropout(0.5))
        # CNN end

        # # DNN layers
        # model.add(Dense(first_layer_size, input_shape=self.input_shape))
        # model.add(Flatten())
        # model.add(Activation('relu'))
        # model.add(Dropout(0.1))
        # # DNN end

        model.add(Dense(second_layer_size))
        model.add(Activation('relu'))
        model.add(Dropout(0.5))

        model.add(Dense(third_layer_size))
        model.add(Activation('relu'))
        model.add(Dropout(0.5))

        model.add(Dense(self.action_size))
        model.add(Activation('linear'))

        model.compile(loss=mean_squared_error,
                      optimizer=Adam(),
                      metrics=['accuracy'])
        LOGGER.info('Model successfully built with hidden layers: {}, {}, {}'
                    .format(first_layer_size,
                            second_layer_size,
                            third_layer_size))
        self.model = model

    def decrease_epsilon(self):
        if self.epsilon > self.min_epsilon:
            self.epsilon -= (1 / self.epochs)
        LOGGER.info('New epsilon is {}'.format(self.epsilon))

    def act(self, state, with_random=True, min_value=1.5):
        if with_random and random.random() < self.epsilon:  # choose random action
            action = np.random.randint(0, self.action_size)
        else:  # choose best action from Q(s,a) values
            q_val = self.model.predict(Agent.df_to_array(state), batch_size=1)
            if not with_random:
                LOGGER.info('\tQ vector: {}'.format(q_val))
                if np.max(q_val[0]) < min_value:
                    return -1
            action = np.argmax(q_val[0])
            LOGGER.info('\t\tChosen action index: {}'.format(action))
        return action

    def remember(self, state, action, reward, next_state, done):
        action_tuple = (state, action, reward, next_state, done)
        self.memory[action].append(action_tuple)
        self.replay_index += 1
        if self.replay_index >= self.replay_buffer:
            self.replay()
            self.replay_index = 0

    def replay(self):
        # randomly sample our experience replay memory
        flat_list = [item for sublist in self.memory.values() for item in sublist]
        mini_batch = random.sample(flat_list, self.replay_buffer)
        LOGGER.info('Experience replay for {} memories'.format(len(mini_batch)))
        # LOGGER.info('Action pool: {}'.format([mem[1] for mem in mini_batch]))

        x_train = []
        y_train = []
        for mem in mini_batch:
            state, action, reward, next_state, done = mem

            state_vals = Agent.df_to_array(state)
            next_state_vals = Agent.df_to_array(next_state)

            old_q = self.model.predict(state_vals, batch_size=1)
            new_q = self.model.predict(next_state_vals, batch_size=1)
            max_q = np.max(new_q)
            update = reward  # 10 if reward > 0 else -10
            if not done:
                update += self.gamma * max_q
            old_q[0][action] = update
            x_train.append(state.values)
            y_train.append(old_q[0])

        x_train = np.array(x_train)  # (replay_buffer, 50, 15)
        y_train = np.array(y_train)  # (replay_buffer, 90)
        self.model.fit(x_train,
                       y_train,
                       batch_size=self.replay_buffer,
                       epochs=16,
                       verbose=0)

    def load(self, name):
        LOGGER.info("Load '%s' model", name)
        self.model.load_weights(name)

    def save(self, name):
        LOGGER.info("Save '%s' model", name)
        self.model.save_weights(name)

    @staticmethod
    def df_to_array(df):
        return np.expand_dims(df.values, axis=0)  # (50, 15) -> (1, 50, 15)
