def mat_mult(a, b): # 手动实现矩阵乘法
    if len(a[0]) != len(b):
        return "矩阵维度不匹配"
    res = [[0 for _ in range(len(b[0]))] for _ in range(len(a))]
    for i in range(len(a)):
        for j in range(len(b[0])):
            for k in range(len(b)):
                res[i][j] += a[i][k] * b[k][j]
    return res
