"""Uses generator functions to supply train/test with data.
Image renderings and text are created on the fly each time"""

from os.path import join
import tensorflow as tf
import numpy as np
import cv2
import random
import preproc.preprocess as pp

char_list = " !\"#&'()*+,-./0123456789:;?ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


class Generator(tf.keras.callbacks.Callback):
    """Generator class to support data streaming"""

    def __init__(self, args, input_shape, batch_size=0):
        self.output = args.OUTPUT
        self.model_output_size = len(char_list) + 1

        self.batch_size = 20 if batch_size == 0 else batch_size
        self.downsample_factor = 4

        # (w, h)
        self.input_shape = input_shape
        self.max_line_length = 120

        self.data_path = args.DATA
        self.ground_truth_path = args.GROUND_TRUTH

        self.train_list = self.read_and_fill(args.TRAIN_FILE)
        self.val_list = self.read_and_fill(args.VALIDATION_FILE)
        self.test_list = self.read_and_fill(args.TEST_FILE)

        self.cur_train_index = 0
        self.cur_val_index = 0
        self.cur_test_index = 0

        self.build_line_lists()

    def read_and_fill(self, txt_file):
        arr = open(txt_file).read().splitlines()
        np.random.shuffle(arr)

        while (len(arr) % self.batch_size) > 0:
            arr.append(random.choice(arr))
        return arr

    def build_line_lists(self):
        """Read and build the lists from txt files of the dataset"""

        def create(partition, lines=[], labels=[], lengths=[]):
            for item in partition:
                txt = open(join(self.ground_truth_path, f"{item}.txt")).read()
                txt = txt.strip()
                # self.max_line_length = max(len(txt), self.max_line_length)
                lines.append(txt)
                lengths.append(float(len(txt)))

            # self.max_line_length = int(np.ceil(self.max_line_length / 10)) * 10
            labels = create_labels(lines)
            lengths = np.expand_dims(np.array(lengths), 1)
            return lines, labels, lengths

        def create_labels(lines):
            labels = np.ones([len(lines), self.max_line_length]) * -1
            for i, line in enumerate(lines):
                labels[i, 0:len(line)] = [char_list.find(c) for c in line]
            return labels

        self.train_lines, self.train_labels, self.train_label_length = create(self.train_list)
        self.val_lines, self.val_labels, self.val_label_length = create(self.val_list)
        self.test_lines, self.test_labels, self.test_label_length = create(self.test_list)

        self.input_length = np.ones([self.batch_size, 1])
        self.input_length *= ((self.input_shape[0] // self.downsample_factor) - 2)

        self.train_steps = len(self.train_lines) // self.batch_size
        self.val_steps = len(self.val_lines) // self.batch_size
        self.test_steps = len(self.test_lines) // self.batch_size

    def next_train(self):
        """Get the next batch from train partition (yield)"""

        def get_batch(index, size):
            args = [self.get_img(self.train_list[index:index + size]),
                    self.train_labels[index:index + size],
                    self.input_length,
                    self.train_label_length[index:index + size],
                    self.train_lines[index:index + size]]
            return self.create_input_output(args)

        while True:
            ret = get_batch(self.cur_train_index, self.batch_size)
            self.cur_train_index += self.batch_size

            if self.cur_train_index >= len(self.train_list):
                self.cur_train_index = 0
            yield ret

    def next_val(self):
        """Get the next batch from validation partition (yield)"""

        def get_batch(index, size):
            args = [self.get_img(self.val_list[index:index + size]),
                    self.val_labels[index:index + size],
                    self.input_length,
                    self.val_label_length[index:index + size],
                    self.val_lines[index:index + size]]
            return self.create_input_output(args)

        while True:
            ret = get_batch(self.cur_val_index, self.batch_size)
            self.cur_val_index += self.batch_size

            if self.cur_val_index >= len(self.val_list):
                self.cur_val_index = 0
            yield ret

    def next_test(self):
        """Get the next batch from test partition (yield)"""

        def get_batch(index, size):
            args = [self.get_img(self.test_list[index:index + size]),
                    self.test_labels[index:index + size],
                    self.input_length,
                    self.test_label_length[index:index + size],
                    self.test_lines[index:index + size]]
            return self.create_input_output(args)

        while True:
            ret = get_batch(self.cur_test_index, self.batch_size)
            self.cur_test_index += self.batch_size

            if self.cur_test_index >= len(self.test_list):
                self.cur_test_index = 0
            yield ret

    def get_img(self, partition):
        """Load image and apply preprocess"""

        inputs = np.zeros((self.batch_size,) + self.input_shape)

        for i, filename in enumerate(partition):
            img_path = join(self.data_path, f"{filename}.png")
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            img = pp.preprocess(img, self.input_shape[1::-1])
            inputs[i] = np.reshape(img, img.shape + (1,))
        return inputs

    def create_input_output(self, args):
        """Create `input and output` format to the model"""

        inputs = {
            'the_inputs': args[0],
            'the_labels': args[1],
            'input_length': args[2],
            'label_length': args[3],
            'source_str': args[4]  # used for visualization only
        }
        # dummy data for dummy loss function
        outputs = {'ctc': np.zeros([self.batch_size])}
        return (inputs, outputs)