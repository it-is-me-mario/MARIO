#%%
import mario

#%%
a = mario.load_test("IOT")
# %%
io = a.to_pymrio("a", "b")
# %%
io.calc_all()
# %%
import cvxpy as cp

# %%
X = cp.Variable(shape=(1, 10), nonneg=True)
Y = cp.log(X)
# %%
obj = cp.Minimize(cp.sum(X))

# %%
prob = cp.Problem(obj, [Y <= 10])
# %%
prob.solve()
# %%
