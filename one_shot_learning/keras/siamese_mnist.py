"""
Trains a Siamese MLP on pairs of digits from the MNIST dataset.
It follows Hadsell-et-al.'06 [1] by computing the Euclidean distance on the
output of the shared network and by optimizing the contrastive loss (see paper
for mode details).
# References
- Dimensionality Reduction by Learning an Invariant Mapping
    http://yann.lecun.com/exdb/publis/pdf/hadsell-chopra-lecun-06.pdf
Gets to 97.2% test accuracy after 20 epochs.
2 seconds per epoch on a Titan X Maxwell GPU
"""
from __future__ import absolute_import
from __future__ import print_function

import argparse
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from tqdm import tqdm

DISTANCE_THRESHOLD = 0.50
NUM_CLASSES = 10
SEED = 42


def euclidean_distance_scalar(vects):
    x, y = vects
    sum_square = tf.keras.backend.sum(tf.square(x - y), axis=1, keepdims=True)
    return tf.keras.backend.sqrt(tf.keras.backend.maximum(sum_square, tf.keras.backend.epsilon()))


def l1_distance_vector(vects):
    x, y = vects
    l1 = tf.abs(x - y)
    return tf.keras.backend.maximum(l1, tf.keras.backend.epsilon())


def contrastive_loss(y_true, y_pred):
    """Contrastive loss from Hadsell-et-al.'06
    http://yann.lecun.com/exdb/publis/pdf/hadsell-chopra-lecun-06.pdf
    """
    margin = 1
    sqaure_pred = tf.keras.backend.square(y_pred)
    margin_square = tf.square(tf.keras.backend.maximum(margin - y_pred, 0))
    return tf.keras.backend.mean(y_true * sqaure_pred + (1 - y_true) * margin_square)


def create_pairs(x, digit_indices):
    """Positive and negative pair creation.
    Alternates between positive and negative pairs.
    """
    pairs = []
    labels = []
    n = min([len(digit_indices[d]) for d in range(NUM_CLASSES)])
    for d in range(NUM_CLASSES):
        for i in range(n - 1):
            for j in range(i + 1, n):
                z1, z2 = digit_indices[d][i], digit_indices[d][j]
                pairs += [[x[z1], x[z2]]]

                rand_inc = np.random.randint(1, NUM_CLASSES)
                rand_idx = np.random.randint(0, len(digit_indices[d]))
                dn = (d + rand_inc) % NUM_CLASSES
                z1, z2 = digit_indices[d][i], digit_indices[dn][rand_idx]
                pairs += [[x[z1], x[z2]]]
                labels += [1, 0]
    return np.array(pairs), np.array(labels)


def create_base_nn_network(input_shape):
    """Base NN network to be shared (eq. to feature extraction).
    """
    inputs = tf.keras.layers.Input(shape=input_shape)
    x = tf.keras.layers.Flatten()(inputs)
    x = tf.keras.layers.Dense(128, kernel_regularizer=tf.keras.regularizers.l2(5e-6))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.225)(x)
    x = tf.keras.layers.Dense(128, kernel_regularizer=tf.keras.regularizers.l2(5e-6))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.225)(x)
    x = tf.keras.layers.Dense(128, activation='relu', kernel_regularizer=tf.keras.regularizers.l2(5e-6))(x)
    return tf.keras.models.Model(inputs, x)


def create_base_cnn_network(input_shape):
    """Base CNN network to be shared (eq. to feature extraction).
    """
    inputs = tf.keras.layers.Input(shape=input_shape)
    x = tf.keras.layers.Conv2D(32, kernel_size=(5, 5), strides=(1, 1), padding='same',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-4))(inputs)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.MaxPool2D()(x)
    x = tf.keras.layers.Dropout(0.225)(x)
    x = tf.keras.layers.Conv2D(64, kernel_size=(3, 3), strides=(1, 1), padding='same',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-4))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.MaxPool2D()(x)
    x = tf.keras.layers.Dropout(0.225)(x)
    x = tf.keras.layers.Flatten()(x)
    x = tf.keras.layers.Dense(128, kernel_regularizer=tf.keras.regularizers.l2(5e-4))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Dense(128, activation='relu', kernel_regularizer=tf.keras.regularizers.l2(5e-4))(x)
    return tf.keras.models.Model(inputs, x)


def create_base_fcn_network(input_shape):
    """Base fully convolutional network to be shared (eq. to feature extraction).
    """
    inputs = tf.keras.layers.Input(shape=input_shape)
    x = tf.keras.layers.Conv2D(32, kernel_size=(7, 7), strides=(1, 1), padding='same',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-5))(inputs)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.4)(x)
    x = tf.keras.layers.Conv2D(64, kernel_size=(5, 5), strides=(2, 2), padding='same',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-5))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Conv2D(64, kernel_size=(3, 3), strides=(1, 1), padding='same',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-5))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Conv2D(128, kernel_size=(3, 3), strides=(2, 2), padding='same',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-5))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Conv2D(128, kernel_size=(3, 3), strides=(1, 1), padding='valid',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-5))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Conv2D(256, kernel_size=(3, 3), strides=(1, 1), padding='valid',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-5))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Conv2D(256, kernel_size=(3, 3), strides=(1, 1), padding='valid',
                               kernel_regularizer=tf.keras.regularizers.l2(5e-5))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Flatten()(x)
    return tf.keras.models.Model(inputs, x)


def create_simple_siamese_model(base_network_model, input_shape):
    if base_network_model == 'nn':
        base_network = create_base_nn_network(input_shape)
    elif base_network_model == 'cnn':
        base_network = create_base_cnn_network(input_shape)
    elif base_network_model == 'fcn':
        base_network = create_base_fcn_network(input_shape)
    else:
        raise Exception('Unknown base network model type.')

    input_a = tf.keras.layers.Input(shape=input_shape)
    input_b = tf.keras.layers.Input(shape=input_shape)
    # because we re-use the same instance `base_network`,
    # the weights of the network
    # will be shared across the two branches
    processed_a = base_network(input_a)
    processed_b = base_network(input_b)
    distance = tf.keras.layers.Lambda(euclidean_distance_scalar)([processed_a, processed_b])
    model = tf.keras.models.Model([input_a, input_b], distance)

    opt = tf.keras.optimizers.RMSprop()  # performed much better than Adam
    model.compile(loss=contrastive_loss, optimizer=opt, metrics=[acc])

    return model


def create_dense_siamese_model(base_network_model, input_shape):
    if base_network_model == 'nn':
        base_network = create_base_nn_network(input_shape)
    elif base_network_model == 'cnn':
        base_network = create_base_cnn_network(input_shape)
    elif base_network_model == 'fcn':
        base_network = create_base_fcn_network(input_shape)
    else:
        raise Exception('Unknown base network model type.')

    input_a = tf.keras.layers.Input(shape=input_shape)
    input_b = tf.keras.layers.Input(shape=input_shape)

    processed_a = base_network(input_a)
    processed_b = base_network(input_b)

    # output_shape=lambda x: x[0]
    embedding = tf.keras.layers.Lambda(l1_distance_vector)([processed_a, processed_b])
    embedding = tf.keras.layers.BatchNormalization()(embedding)
    x = tf.keras.layers.Dropout(0.5)(embedding)
    x = tf.keras.layers.Dense(512, kernel_regularizer=tf.keras.regularizers.l2(5e-4))(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Activation('relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    prediction = tf.keras.layers.Dense(1, kernel_regularizer=tf.keras.regularizers.l2(5e-4),
                                       activation='sigmoid')(x)
    model = tf.keras.models.Model([input_a, input_b], prediction)

    opt = tf.keras.optimizers.RMSprop()
    model.compile(loss='binary_crossentropy', optimizer=opt, metrics=['accuracy'])

    return model


def compute_accuracy(y_true, y_pred):
    """Compute classification accuracy with a fixed threshold on distances.
    """
    pred = y_pred.ravel() < DISTANCE_THRESHOLD
    return np.mean(pred == y_true)


def acc(y_true, y_pred):
    """Compute classification accuracy with a fixed threshold on distances.
    """
    return tf.keras.backend.mean(tf.equal(y_true, tf.cast(y_pred < DISTANCE_THRESHOLD, y_true.dtype)))


def get_digit_indices(labels, examples_per_class):
    digit_indices = [np.where(labels == i)[0] for i in range(NUM_CLASSES)]
    return [di[:examples_per_class] for di in digit_indices]


def plot_values(train_values, valid_values, y_label):
    epochs = range(1, len(train_values) + 1)
    plt.clf()
    plt.plot(epochs, train_values, 'b')
    if valid_values is not None:
        plt.plot(epochs, valid_values, 'g')
    plt.xlabel('Epochs')
    plt.ylabel(y_label)
    plt.show()


def plot_examples_separated(image_pairs, labels, predictions):
    num = image_pairs.shape[0]
    fig = plt.figure(1)
    for i in range(0, num):
        # works because labels are alternating in unshuffled dataset
        img0 = image_pairs[i, 0][:, :, 0]
        img1 = image_pairs[i, 1][:, :, 0]
        label = labels[i]
        distance = predictions[i, 0]
        fig.add_subplot(num // 2, 4, (i * 2 + 1))
        plt.imshow(img0)
        fig.add_subplot(num // 2, 4, (i * 2 + 2))
        plt.imshow(img1)
        plt.xlabel('==' if label == 0 else '!=')
        plt.ylabel('{:.4f}'.format(distance))
    plt.show()


def plot_examples(image_pairs, predictions):
    num = image_pairs.shape[0]
    fig = plt.figure(1)
    for i in range(0, num):
        img0 = image_pairs[i, 0][:, :, 0]
        img1 = image_pairs[i, 1][:, :, 0]
        distance = predictions[i, 0]
        fig.add_subplot(num, 2, (2 * i + 1))
        plt.imshow(img0)
        fig.add_subplot(num, 2, (2 * i + 2))
        plt.imshow(img1)
        plt.ylabel('{:.4f}'.format(distance))
    plt.show()


def main(args):
    # results can still be non-deterministic when running on GPU, due to cuDNN
    tf.set_random_seed(SEED)
    np.random.seed(SEED)

    # the data, split between train and test sets
    (x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
    x_train = np.expand_dims(x_train, axis=-1).astype('float32')
    x_test = np.expand_dims(x_test, axis=-1).astype('float32')
    x_train /= 255
    x_test /= 255

    # create training+test positive and negative pairs
    tr_digit_indices = get_digit_indices(y_train, args.examples_per_class)
    tr_pairs, tr_y = create_pairs(x_train, tr_digit_indices)

    te_digit_indices = get_digit_indices(y_test, args.examples_per_class)
    te_pairs, te_y = create_pairs(x_test, te_digit_indices)

    # network definition
    input_shape = x_train.shape[1:]

    if args.model == 'simple_head':
        model = create_simple_siamese_model(args.base_network, input_shape)
    elif args.model == 'dense_head':
        model = create_dense_siamese_model(args.base_network, input_shape)
    else:
        raise Exception('Unknown model type.')

    model.summary()

    # train

    callbacks = []
    if args.early_stopping:
        callbacks.append(tf.keras.callbacks.EarlyStopping(patience=20, monitor='val_acc'))
    callbacks.append(tf.keras.callbacks.ReduceLROnPlateau(monitor='val_acc', factor=0.5, patience=10, verbose=1))
    callbacks.append(tf.keras.callbacks.ModelCheckpoint(
        filepath='checkpoints/ckp',
        monitor='val_acc',
        verbose=1,
        save_best_only=True,
        save_weights_only=True,
        period=1))

    if args.min_epochs:
        print('Pre-training...')
        # we pre-train the model (some steps without early stopping), because it takes a while
        # until the accuracy starts to improve
        model.fit([tr_pairs[:, 0], tr_pairs[:, 1]], tr_y,
                  batch_size=args.batch_size,
                  epochs=args.min_epochs,
                  verbose=2,
                  validation_data=([te_pairs[:, 0], te_pairs[:, 1]], te_y))

    print('Training...')
    history = model.fit([tr_pairs[:, 0], tr_pairs[:, 1]], tr_y,
                        batch_size=args.batch_size,
                        epochs=args.max_epochs,
                        initial_epoch=args.min_epochs,
                        callbacks=callbacks,
                        verbose=2,
                        validation_data=([te_pairs[:, 0], te_pairs[:, 1]], te_y))

    plot_values(history.history['loss'], history.history['val_loss'], 'Loss')
    plot_values(history.history['acc'], history.history['val_acc'], 'Accuracy')

    # load the best model from checkpoint
    latest = tf.train.latest_checkpoint('checkpoints')
    model.load_weights(latest)

    # compute final accuracy on training and test sets
    tr_pred = model.predict([tr_pairs[:, 0], tr_pairs[:, 1]])
    te_pred = model.predict([te_pairs[:, 0], te_pairs[:, 1]])

    if args.model == 'simple_head':
        tr_acc = compute_accuracy(tr_y, tr_pred)
        te_acc = compute_accuracy(te_y, te_pred)
    else:
        tr_scores = model.evaluate([tr_pairs[:, 0], tr_pairs[:, 1]], tr_y, verbose=2)
        tr_acc = tr_scores[1]
        te_scores = model.evaluate([te_pairs[:, 0], te_pairs[:, 1]], te_y, verbose=2)
        te_acc = te_scores[1]

    print('>>> Accuracy on training set: {:.2f}%'.format(tr_acc * 100))
    print('>>> Accuracy on test set:     {:.2f}%'.format(te_acc * 100))

    # plot first 20 examples
    image_pairs = te_pairs[:20, :]
    labels = te_y[:20]
    predictions = te_pred[:20]

    plot_examples_separated(image_pairs, labels, predictions)

    # plot first 10 FPs
    if args.model == 'simple_head':
        # minimum
        assessment_criteria = lambda new, prev: new < prev
    else:
        # maximum
        assessment_criteria = lambda new, prev: new > prev

    image_pairs = []
    labels = np.zeros(10)
    predictions = np.zeros((10, 1))
    index = 0
    while len(image_pairs) < 10:
        if assessment_criteria(te_pred[index], DISTANCE_THRESHOLD) and te_y[index] == 0:
            image_pairs += [[te_pairs[index, 0], te_pairs[index, 1]]]
            labels[len(image_pairs) - 1] = te_y[index]
            predictions[len(image_pairs) - 1, 0] = te_pred[index, 0]
        index += 1
    image_pairs = np.array(image_pairs)

    plot_examples(image_pairs, predictions)

    # plot first 10 FNs
    image_pairs = []
    labels = np.zeros(10)
    predictions = np.zeros((10, 1))
    index = 0
    while len(image_pairs) < 10:
        if not assessment_criteria(te_pred[index], DISTANCE_THRESHOLD) and te_y[index] == 1:
            image_pairs += [[te_pairs[index, 0], te_pairs[index, 1]]]
            labels[len(image_pairs) - 1] = te_y[index]
            predictions[len(image_pairs) - 1, 0] = te_pred[index, 0]
        index += 1
    image_pairs = np.array(image_pairs)

    plot_examples(image_pairs, predictions)

    # classify (using minimum distance)
    print('Classifying test set...')
    min_correct_counter = 0
    median_correct_counter = 0
    mean_correct_counter = 0
    for t in tqdm(range(x_test.shape[0])):
        test_img = x_test[t]
        test_img_label = y_test[t]
        n = min([len(tr_digit_indices[d]) for d in range(NUM_CLASSES)]) - 1

        if args.model == 'simple_head':
            # minimum
            assessment_criteria = lambda new, prev: new < prev
            min_aggregated_distance = 999
            mean_aggregated_distance = 999
            median_aggregated_distance = 999
        else:
            # maximum
            assessment_criteria = lambda new, prev: new > prev
            min_aggregated_distance = -999
            mean_aggregated_distance = -999
            median_aggregated_distance = -999

        min_aggregated_distance_label = -1
        mean_aggregated_distance_label = -1
        median_aggregated_distance_label = -1

        for d in range(NUM_CLASSES):
            image_pairs = []
            for i in range(n):
                z1 = tr_digit_indices[d][i]
                img = x_train[z1]
                image_pairs += [[img, test_img]]
            image_pairs = np.array(image_pairs)
            predictions = model.predict([image_pairs[:, 0], image_pairs[:, 1]])

            min_distance = np.min(predictions)
            if assessment_criteria(min_distance, min_aggregated_distance):
                min_aggregated_distance = min_distance
                min_aggregated_distance_label = d

            median_distance = np.median(predictions)
            if assessment_criteria(median_distance, median_aggregated_distance):
                median_aggregated_distance = median_distance
                median_aggregated_distance_label = d

            mean_distance = np.mean(predictions)
            if assessment_criteria(mean_distance, mean_aggregated_distance):
                mean_aggregated_distance = mean_distance
                mean_aggregated_distance_label = d

        if test_img_label == min_aggregated_distance_label:
            min_correct_counter += 1

        if test_img_label == median_aggregated_distance_label:
            median_correct_counter += 1

        if test_img_label == mean_aggregated_distance_label:
            mean_correct_counter += 1

    print('Classification accuracy using MIN:    {}'.format(min_correct_counter / x_test.shape[0]))
    print('Classification accuracy using MEDIAN: {}'.format(median_correct_counter / x_test.shape[0]))
    print('Classification accuracy using MEAN:   {}'.format(mean_correct_counter / x_test.shape[0]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()  # TODO augmentation param
    parser.add_argument('--min_epochs', type=int, default=0,
                        help='The minimum number of (pre-)training epochs, before early-stopping kicks in')
    parser.add_argument('--max_epochs', type=int, default=500,
                        help='The maximum number of training epochs')
    parser.add_argument('--batch_size', type=int, default=16,
                        help='The batch size while training')
    parser.add_argument('--examples_per_class', type=int, default=25,
                        help='Maximum number of examples per class')
    parser.add_argument('--model', choices=['simple_head', 'dense_head'], type=str, default='dense_head',  # TODO feature-wise-dense https://www.kaggle.com/seesee/siamese-pretrained-0-822
                        help='The network model of the siamese, which mainly differs in the head model used')
    parser.add_argument('--base_network', choices=['fcn', 'cnn', 'nn'], type=str, default='cnn',
                        help='The base network model used in the siamese')
    parser.add_argument('--early_stopping', type=bool, default=True,
                        help='Whether to use early stopping or not')
    args = parser.parse_args()
    main(args)
