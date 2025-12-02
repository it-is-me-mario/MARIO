#%%
import numpy as np
import pandas as pd
from scipy.optimize import minimize

def ras(Z, target_rows, target_cols, tol=1e-8, max_iter=1000):
    """
    Perform RAS algorithm (biproportional fitting).

    Parameters
    ----------
    A : numpy.ndarray
        Initial input-output matrix (n x m).
    target_rows : numpy.ndarray
        Desired row sums (length n).
    target_cols : numpy.ndarray
        Desired column sums (length m).
    tol : float
        Convergence tolerance for row/column sums.
    max_iter : int
        Maximum number of iterations.

    Returns
    -------
    A_new : numpy.ndarray
        Adjusted matrix with row and column sums matching targets.
    """

    if isinstance(Z,pd.DataFrame):
        Z = Z.values
        
    Z_new = Z.copy().astype(float)

    iteration = 0
    while iteration<=max_iter:

        # Scale rows
        row_sums = Z_new.sum(axis=1)
        row_factors = np.divide(target_rows, row_sums, out=np.ones_like(target_rows), where=row_sums!=0)
        Z_new = (Z_new.T * row_factors).T

        # Scale columns
        col_sums = Z_new.sum(axis=0)
        col_factors = np.divide(target_cols, col_sums, out=np.ones_like(target_cols), where=col_sums!=0)
        Z_new = Z_new * col_factors

        # Check convergence
        if (np.allclose(Z_new.sum(axis=1), target_rows, atol=tol) and
            np.allclose(Z_new.sum(axis=0), target_cols, atol=tol)):
            break

    return Z_new

# FIXME --> Add get_excel, read_excel function to do the balance.

def maxent(Z0, target_rows, target_cols, tol=1e-10):
    """
    Balance an input-output (transactions) matrix using the Maximum Entropy approach.

    #FIXME ---> consider the possibility to use both z,Z

    Parameters
    ----------
    Z0 : np.ndarray
        Original transactions matrix (n x m)
    target_rows : np.ndarray
        Desired row sums (length n)
    target_cols : np.ndarray
        Desired column sums (length m)
    tol : float
        Tolerance for clipping to avoid log(0)

    Returns
    -------
    Z_balanced : np.ndarray
        Balanced transactions matrix
    """
    n, m = Z0.shape
    z0_flat = Z0.flatten()

    # Objective: cross-entropy relative to original matrix
    def objective(z):
        z = np.clip(z, tol, None)  # avoid log(0)
        return np.sum(z * np.log(z / z0_flat))

    # Constraints: row sums and column sums
    constraints = []
    for i in range(n):
        constraints.append({
            'type': 'eq',
            'fun': lambda z, i=i: np.sum(z.reshape(n, m)[i, :]) - target_rows[i]
        })
    for j in range(m):
        constraints.append({
            'type': 'eq',
            'fun': lambda z, j=j: np.sum(z.reshape(n, m)[:, j]) - target_cols[j]
        })

    # Bounds: non-negative entries
    bounds = [(0, None) for _ in range(n*m)]

    # Initial guess: scale prior matrix to match total sum
    z_init = z0_flat * (target_rows.sum() / z0_flat.sum())

    # Solve optimization
    result = minimize(objective, z_init, bounds=bounds, constraints=constraints, method='SLSQP')

    if not result.success:
        raise RuntimeError("MaxEnt optimization did not converge: " + result.message)

    Z_balanced = result.x.reshape(n, m)
    return Z_balanced

if __name__ == "__main__":

    # # Original transactions matrix Z
    # Z = np.array([
    #     [2, 3, 5],
    #     [4, 2, 4],
    #     [3, 5, 2]
    # ], dtype=float)

    # # Target row sums
    # target_rows = np.array([10., 12., 11.])

    # # Target column sums
    # target_cols = np.array([9., 11., 13.])

    # Z_new = ras(Z,target_rows,target_cols,)


    # max ent
    Z0 = np.array([
        [2, 3, 5],
        [4, 2, 4],
        [3, 5, 2]
    ], dtype=float)

    target_rows = np.array([10., 12., 11.])
    target_cols = np.array([9., 11., 13.])

    Z_maxent = maxent(Z0, target_rows, target_cols)

    print("Balanced Z (MaxEnt):\n", np.round(Z_maxent, 8))
    print("Row sums:", np.round(Z_maxent.sum(axis=1), 8))
    print("Col sums:", np.round(Z_maxent.sum(axis=0), 8))

# %%
