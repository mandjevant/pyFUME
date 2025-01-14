import simpful 

class SimpfulConverter(object):
    """    This object converts a description of a Fuzzy System into a readable
        Simpful project file.

        Args:
            input_variables_names: The names of the input variables of the fuzzy model.
            consequents_matrix: The parameters of the consequent function.
            fuzzy_sets: list containing a sub-list for each fuzzy set in the model. The sub-list should contain the shape of the fuzzy set (e.g. 'gauss') and the parameters of the function (e.g. mu, sigma). For example: ('gauss', 5, 1).
            model_order: The order of the fuzzy model ('zero' or 'first') (default = 'first').
            fuzzy_sets_to_drop: Fuzzy sets that should be disabled in the Simpful code, for example when flagged by GRABS for simplification (default = None).
            extreme_values: The values that should be used for the universe of discourse for the vaiables in the fuzzy model (default = None).
            operators: A list of strings, specifying fuzzy operators to be used instead of defaults (default = None). For more information see Simpful's documentation.
            verbose: Boolean (True/False) that indicates whether extra information will be printed in the user's console (default = True).

    """
    
    def __init__(self, 
            input_variables_names,
            consequents_matrix,
            fuzzy_sets,
            model_order = 'first',
            fuzzy_sets_to_drop = None,
            extreme_values = None,
            operators = None,
            verbose = False):
        super().__init__()
        self._input_variables = input_variables_names
        self._consequents_matrix = consequents_matrix
        self._clusters = len(self._consequents_matrix)
        self._fuzzy_sets = fuzzy_sets
        self._model_order = model_order
        self._fuzzy_sets_to_drop = fuzzy_sets_to_drop
        self._extreme_values = extreme_values
        self.verbose = verbose
        if self._fuzzy_sets_to_drop==None:
            self._fuzzy_sets_to_drop={}

        if self._model_order == 'first':  
            assert(len(self._input_variables)+1 == len(self._consequents_matrix[0]))
        
        if self.verbose: print(" * Detected %d rules / clusters" % self._clusters)

        self._source_code = []
        self._source_code.append( '# WARNING: this source code was automatically generated by pyFUME.' )
        self._source_code.append( "from simpful import *" )
        if operators is None:
            self._source_code.append("\nFS = FuzzySystem(show_banner=False)")
        else:
            # experimental, please test ASAP
            self._source_code.append("\nFS = FuzzySystem(operators="+str(operators)+")")

        
    def save_code(self, path):
        """
            Saves the Simpful code.
            
            Args:
                path: Path to the folder where the Simpful code should be saved.
        """
        code = self.generate_code()
        with open(path, "w") as fo:
            fo.write(code)
        if self.verbose == True:
            print (" * Code saved to file %s" % path)

    def generate_object(self):
        """
            Generates the executable object containing the fuzzy model.
        """
        code = self.generate_code()
        if self.verbose:
            exec(code, globals()) 
        elif self.verbose == False:
            import os
            import contextlib
            with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
                exec(code, globals()) 
        
        from copy import deepcopy
        self._fuzzyreasoner = deepcopy(FS)

    def generate_code(self):
        """
            Generates the Simpful code.
        """
        # rules
        rule_texts = self.create_rules()
        for i in range(1, self._clusters+1):
            self._source_code.append('RULE%d = "%s"' % (i, rule_texts[i-1]))
        self._source_code.append("FS.add_rules([%s])" % (", ". join(["RULE%d" % i for i in range(1,self._clusters+1)])))

        self._source_code.append("")

        # output functions
        
        if self._model_order == 'first':
            B = self._create_consequents()
            for i in range(self._clusters):
                self._source_code.append("FS.set_output_function('%s', '%s')" % ("fun%d" % (i+1),  B[i]))
        elif self._model_order == 'zero':
            for i in range(self._clusters):
                self._source_code.append("FS.set_crisp_output_value('%s', %s)" % ("fun%d" % (i+1),  self._consequents_matrix[i]))
        else:
            raise Exception("Model order not supported,"+self._model_order)
        self._source_code.append("")
    
        # fuzzy sets and membership functions
        result = self._create_fuzzy_sets()
        self._source_code.append(result)

        self._source_code.append("# end of automatically generated code #")

        return "\n".join(self._source_code)


    def _create_fuzzy_sets(self):
        
        j=0
        chunk = ""
        
        for num_var, var in enumerate(self._input_variables):

            subchunk = []
            for cluster in range(self._clusters):

                if (num_var, cluster) in self._fuzzy_sets_to_drop:
                    chunk+="# "

                #if self.verbose: print (" * Creating fuzzy set for variable %s, cluster%d" % (var, cluster+1))
                
                chunk += 'FS_%d = FuzzySet(' % (j+1)
                term = 'cluster%d' % (cluster+1)
                                
                fstype, params = self._fuzzy_sets[j]
                if fstype == 'gauss':
                    chunk += "function=Gaussian_MF(%f, %f), term='%s')" % (params[0], params[1], term) 
 
                elif fstype == 'gauss2':
                    chunk += "function=DoubleGaussian_MF(%f, %f, %f, %f), term='%s')" % (params[0], params[1], params[2], params[3], term) 

                elif fstype == 'sigmoid':
                    chunk += "function=Sigmoid_MF(%f, %f), term='%s')" % (params[0], params[1], term) 

                elif fstype == 'invgauss':
                    chunk += "function=InvGaussian_MF(%f, %f), term='%s')" % (params[0], params[1], term) 
                else:
                    raise Exception("Fuzzy set type not supported,"+fstype)
                if (num_var, cluster) not in self._fuzzy_sets_to_drop:
                    subchunk.append("FS_%d" % (j+1))
                #print ( self._fuzzy_sets[j] )
                j += 1
                chunk += "\n"
                # print(chunk)
            if self._extreme_values == None:
                chunk += "MF_%s = LinguisticVariable([%s], concept='%s')\n" % (var, ", ".join(subchunk), var )
            else:
                chunk += "MF_%s = LinguisticVariable([%s], concept='%s' , universe_of_discourse=%s)\n" % (var, ", ".join(subchunk), var, self._extreme_values[num_var] )
            chunk += "FS.add_linguistic_variable('%s', MF_%s)\n\n" % (var, var)

        return chunk

    def _create_consequents(self):
        result = []
        for row in self._consequents_matrix:
            result.append(("+".join(["%e*%s" % (value, name) for (name, value) in zip(self._input_variables, row[:-1])])))
            result[-1] += "+%e" % row[-1]
        return result

    def _create_antecedents(self):

        result = []

        for i in range(self._clusters):
            
            pieces = []
            for j, var in enumerate(self._input_variables):
                value = "cluster%d"% (i + 1)
                if (j,i) in self._fuzzy_sets_to_drop.keys():
                    value = "cluster%d" % (self._fuzzy_sets_to_drop[(j, i)] + 1)
                pieces.append("(%s IS %s)" % (var, value)) 
                
            chunk = (" AND ".join(pieces))
            result.append( chunk )

        return result
        
    def create_rules(self):
        A = self._create_antecedents()
        # B = self._create_consequents()
        B = ["fun%d" % (i+1) for i in range(self._clusters)]
        result = ["IF %s THEN (OUTPUT IS %s)" % (a,b) for a,b in zip(A,B)]
        return result


if __name__ == '__main__':
    
    SC = SimpfulConverter(
        input_variables_names = ["pippo", "pluto"],
        consequents_matrix = [[1,2,3], 
                              [2,3,5]],
        fuzzy_sets = [
                ["gauss", [0,1]],
                ["sigmoid", [1,2]],
                ["gauss2", [0,1,2,3]],
                ["invgauss", [0,1]]
                ]
    )
    
    SC.save_code("TEST.py")
    SC.generate_object()
    print(FS._mfs['pippo'])
    a