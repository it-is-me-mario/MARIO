"""User-defined constants for symbolic optimization problems.

This module allows you to define custom constant generation functions that 
extend the built-in constants available in cvxlab. Custom constants are 
automatically registered when this module is imported, and can be used in defining
constant types as property of variables in model settings.

Usage
-----
Simply define your custom constant in this file as a regular function. 
Each function will be automatically available as a constant type in model settings.
The function is getting as input the dimension of the constant to generate (as a 
Tuple of integers representing rows and columns lengths), and returns as output
the generated constant (as a numpy array or scipy sparse matrix).

Function definition guidelines
------------------------------

1. Use clear, descriptive function names
2. Include comprehensive docstrings with Args, Returns, and Raises sections
3. Accept dimension as a Tuple[int] representing the shape (rows, cols)
4. Return numpy arrays or scipy sparse matrices
5. Include type hints for better code clarity
6. Validate inputs to ensure dimensions are valid tuples of integers
7. Raise appropriate exceptions for invalid inputs


Common patterns
---------------

- Vector validation: len(dimension) == 2 and any(i == 1 for i in dimension)
- Matrix validation: len(dimension) == 2 and all(i > 0 for i in dimension)
- Get size from vector: size = max(dimension)
- Reshape to dimension: array.reshape(dimension)


Import required libraries
-------------------------
Make sure to import necessary libraries at the top of this file (already required
by cvxlab): numpy is commonly used, but you can import others as needed.

For more examples, refer to:
    cvxlab/support/util_constants.py

Example - 'identity matrix' constant
------------------------------------

Example implementation::

    import numpy as np

    def identity_matrix(dimension: Tuple[int]) -> np.array:
        '''Generate a (square) identity matrix of the specified dimension.

        Args:
            dimension (Tuple[int]): The dimension of the matrix row/col.

        Returns:
            np.ndarray: A square identity matrix of the specified dimension.

        Raises:
            TypeError: If passed dimension is not a tuple containing integers,
                or if it does not represent a vector (i.e., at least one element 
                must be equal to 1).
            ValueError: If passed dimension does not represent a vector shape.
        '''
        if not isinstance(dimension, Tuple) or not all(isinstance(i, int) for i in dimension):
            raise TypeError(
                "Constant definition | Identity matrix constant accepts as argument"
                "only a tuple of integers.")

        if len(dimension) != 2 or not any(i == 1 for i in dimension):
            raise ValueError(
                "Constant definition | Identity matrix accetps as argument a tuple "
                "representing a vector only (one dimension). Check variable shape.")

        return np.eye(max(dimension))
"""
import numpy as np
from typing import List

def set1and2_to_set1(dimension: List[int]) -> np.array:
    """Create a special-identity block diagonal matrix mapping set1 x set2 -> set1.
    Args:
        dimension: Tuple[int]: The dimensions of the two sets as (set1, set2).
    Returns:
        np.ndarray: Matrix of shape (set1 * set2, set1) and contains
        ones when the element of set1 in rows and columns match, zeros elsewhere.
    """
    # Validate and normalize set1
    rows, cols = dimension

    if isinstance(rows, int):
        if rows < 1:
            raise ValueError(
                "Constant definition | set1and2_to_set1 requires a non-zero integer for rows (row of dimension touple)"
            )
    else:
        raise TypeError(
            "Constant definition | set1and2_to_set1 accepts as argument only a touple as dimension"
        )

    if isinstance(cols, int):
        if cols < 1:
            raise ValueError(
                "Constant definition | set1and2_to_set1 requires a non-zero integer for cols (column of dimension touple)."
            )
    else:
        raise TypeError(
            "Constant definition | set1and2_to_set1 accepts as argument a touple as dimension"
        )

    set2 = rows // cols

    matrix = np.zeros((rows, cols), dtype=float)
    ones_vector = np.ones(set2, dtype=float)
    for j in range(cols):
        start = j * set2
        matrix[start:start + set2, j] = ones_vector

    return matrix

def anti_identity_matrix(dimension: List[int]) -> np.array:
    """Generate a (square) anti-identity matrix of the specified dimension.

    Args:
        dimension (List[int]): The dimension of the matrix row/col.

    Returns:
        np.ndarray: A square anti-identity matrix of the specified dimension.

    Raises:
        ValueError: If passed dimension is not a list containing integers,
            or if it does not represent a vector (i.e., at least one element 
            must be equal to 1).
    """

    if not isinstance(dimension, List) or not all(isinstance(i, int) for i in dimension):
            raise TypeError(
                "Constant definition | Anti-dentity matrix constant accepts as argument"
                "only a tuple of integers.")
    size = max(dimension)
    return np.ones((size, size)) - np.eye(size)

def my_identity_matrix(dimension: List[int]) -> np.array:
        '''Generate a (square) identity matrix of the specified dimension.

        Args:
            dimension (Tuple[int]): The dimension of the matrix row/col.

        Returns:
            np.ndarray: A square identity matrix of the specified dimension.

        Raises:
            TypeError: If passed dimension is not a tuple containing integers,
                or if it does not represent a vector (i.e., at least one element 
                must be equal to 1).
            ValueError: If passed dimension does not represent a vector shape.
        '''
        if not isinstance(dimension, List) or not all(isinstance(i, int) for i in dimension):
            raise TypeError(
                "Constant definition | Identity matrix constant accepts as argument"
                "only a tuple of integers.")

        if len(dimension) != 2 or not dimension[0] == dimension[1]:
            raise ValueError(
                "Constant definition | Identity matrix can only be square "
                " Check variable shape.")

        return np.eye(max(dimension))