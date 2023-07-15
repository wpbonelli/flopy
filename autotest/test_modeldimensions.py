from flopy.mf6.coordinates import modeldimensions as md


def test_get_data_shape():
    pass


def test_build_shape_expression_empty():
    exp = md.ModelDimensions.build_shape_expression([])
    assert not any(exp)


def test_build_shape_expression():
    exp = md.ModelDimensions.build_shape_expression([":"])
    assert exp == [[":"]]

    exp = md.ModelDimensions.build_shape_expression(["nodes"])
    assert exp == [["nodes"]]
