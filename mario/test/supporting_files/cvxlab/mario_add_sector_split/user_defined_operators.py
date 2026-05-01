"""User-defined operators for symbolic optimization problems.

This module allows you to define custom operators that extend the built-in 
operators available in cvxlab. Custom operators are automatically registered 
when this module is imported, ready to be used as symbolic operators in defining
symbolic problems.

Usage
-----
Simply define the custom operators as standard functions in this file. 
The operator can be used in defining symbolic problem expressions simply by
writing its name followed by parentheses containing the required arguments (defined 
as problems variables).

Function definition guidelines
------------------------------

1. Use clear, descriptive function names
2. Include comprehensive docstrings with Args, Returns, and Raises sections
3. Accept cvxpy Parameters, Constants, or Expressions as inputs
4. Return cvxpy Parameters, Constants, or Expressions as outputs
5. Include type hints for better code clarity
6. Validate input types and values with appropriate error handling
7. Use numpy for numerical computations on parameter values


Import required libraries
-------------------------
Make sure to import necessary libraries at the top of this file (already required
by cvxlab): numpy and cvxpy are commonly used, but you can import others as needed.

For more examples, refer to:
    cvxlab/support/util_operators.py


Example - 'power' operator
--------------------------

Example implementation::

    import numpy as np
    import cvxpy as cp

    def power(
            base: cp.Parameter | cp.Expression,
            exponent: cp.Parameter | cp.Expression,
    ) -> cp.Parameter:
        '''Calculate the element-wise power of a matrix or scalar.

        This funciton calculates the element-wise power of the base, provided an 
        exponent. Either base or exponent can be a scalar.

        Args:
            base (cp.Parameter | cp.Expression): The base for the power operation. 
                The corresponding value can be a scalar or a 1-D numpy array.
            exponent (cp.Parameter | cp.Expression): The exponent for the power 
                operation. The corresponding value can be a scalar or a 1-D numpy array.

        Returns:
            cp.Parameter: A new parameter with the same shape as the input parameters, 
                containing the result of the power operation.

        Raises:
            ValueError: If the base and exponent do not have the same shape and 
                neither is a scalar.
        '''
        if base.shape != exponent.shape:
            if base.is_scalar() or exponent.is_scalar():
                pass
            else:
                raise ValueError(
                    "Base and exponent must have the same shape. In case of "
                    "different shapes, one must be a scalar. "
                    f"Shapes -> base: {base.shape}, exponent: {exponent.shape}.")

        base_val: np.ndarray = base.value
        exponent_val: np.ndarray = exponent.value

        power = np.power(base_val, exponent_val)
        return cp.Parameter(shape=power.shape, value=power)
"""
import numpy as np
import cvxpy as cp
from scipy import sparse as sp


def entropy(A,A0):
    """Calculate the Kullback-Leibler divergence between two matrices.
    Args:
        A: The first matrix.
        A0 : The second matrix.
    Returns:
        cp.Parameter | cp.Expression: The Kullback-Leibler divergence between A and A0.
        entropy(A,A0) = rel_entr(A,A0) = A * log(A / A0)
    """
    #Not used kl_div because it includes -A + A0 terms
    #Scipy function rel_entr is equivalent to A * log(A / A0) and is 0 when A=0
    return cp.rel_entr(A+0.00001,A0+0.00001) 


def block_diag(
        matrix: cp.Parameter | cp.Expression,
        n: cp.Parameter | None = None,
) -> cp.Parameter:
    """Return the matrix itself, or a block-diagonal matrix with the matrix repeated n times.

    Args:
        matrix (cp.Parameter | cp.Expression): The input matrix (must be 2-D).
        n (int | None): Number of times to repeat the matrix on the diagonal.
            If None or not provided, the matrix is returned unchanged.

    Returns:
        cp.Parameter: The original matrix if n is None, otherwise
            a block-diagonal cp.Parameter of shape (rows*n, cols*n) with the input
            matrix on each diagonal block and zeros elsewhere.

    Raises:
        ValueError: If matrix is not 2-D or n is not a positive integer.
    """
    if n is None:
        return matrix
    
    if hasattr(n, 'value'):
        n = n.value  # unwrap cp.Constant / cp.Parameter
    if not len(n) == 1:
        raise ValueError(
            f"N must be a scalar. Passed dimension: '{len(n)}'.")
    n = int(n[0][0])

    # --- validation ---
    if matrix.ndim != 2:
        raise ValueError(
            f"matrix must be 2-D, got shape {matrix.shape}"
        )
    if not isinstance(n, int) or n < 1:
        raise ValueError(
            f"n must be a positive integer, got {n!r}"
        )

    if n == 1:
        return matrix

    # --- build the block-diagonal value ---
    raw = matrix.value  # scipy sparse or numpy array

    if raw is None:
        raise ValueError(
            "matrix.value is None — the Parameter must have a value assigned "
            "before calling block_diag."
        )

    # Normalise to sparse so block_diag always returns a sparse matrix.
    # This preserves efficiency for large, mostly-zero matrices.
    if not sp.issparse(raw):
        raw = sp.csr_matrix(raw)

    result = sp.block_diag([raw] * n, format="csr").toarray()
    
    return cp.Constant(result)