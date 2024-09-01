import numpy as np

w2v_filename = r'Q:\Courses\General\Hebrew-Word2Vec-ronshm\Hebrew-Word2Vec\twitter-w2v\words_vectors.npy'
wordlist_filename = r'Q:\Courses\General\Hebrew-Word2Vec-ronshm\Hebrew-Word2Vec\twitter-w2v\words_list.txt'

w2v_heb = np.load(w2v_filename)
wordlist = open(wordlist_filename, 'r', encoding="utf-8").read().split('\n')
print(w2v_heb.shape)
print(len(wordlist))

from gensim.models import KeyedVectors

words = wordlist
vectors = w2v_heb
model = KeyedVectors(vectors.shape[1])
model.add(words, vectors)
print(model.most_similar('אישה'))
print(model.most_similar('איש'))
