import pandas as pd

train_data = pd.read_csv('train.csv')


from sklearn.utils import shuffle

train_data = shuffle(train_data)



y_column = 'count'
x_columns = [col for col in train_data.columns if col!=y_column]


x = train_data[x_columns]
y = train_data[y_column]

from sklearn.model_selection import train_test_split
x_train, x_test, y_train, y_test = \
    train_test_split(x, y, test_size=0.33, random_state=4)

print(x_train)

from sklearn.preprocessing import StandardScaler
sc = StandardScaler()
x_train = sc.fit_transform(x_train)
x_test = sc.transform(x_test)





