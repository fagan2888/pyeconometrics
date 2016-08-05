# -*- coding: utf-8 -*-
"""
Created on Fri Jun 17 15:13:54 2016

@author: Nicolas
"""

import numpy as np
from numpy.linalg import inv
import scipy.stats as st
from math import exp, sqrt, log, factorial
import matplotlib.pyplot as plt
    
def norm_cdf(x):
    a1 =  0.254829592
    a2 = -0.284496736
    a3 =  1.421413741
    a4 = -1.453152027
    a5 =  1.061405429
    p  =  0.3275911
    sign = 1
    if x < 0:
        sign = -1
    x = abs(x)/sqrt(2.0)
    t = 1.0/(1.0 + p*x)
    y = 1.0 - (((((a5*t + a4)*t) + a3)*t + a2)*t + a1)*t*exp(-x*x)
    return 0.5*(1.0 + sign*y)
    
def unique_permutations(seq):
    i_indices = range(len(seq)-1, -1, -1)
    k_indices = i_indices[1:]
    seq = sorted(seq)
    while True:
        yield seq
        for k in k_indices:
            if seq[k] < seq[k+1]:
                break
        else:
            return
        k_val = seq[k]
        for i in i_indices:
            if k_val < seq[i]:
                break
        (seq[k], seq[i]) = (seq[i], seq[k])
        seq[k+1:] = seq[-1:k:-1]

def nCr(n,r):
    try:
        return factorial(n) / factorial(r) / factorial(n-r)
    except:
        return 101
    


    
class FEPanelLogit():
    def response_function(self, X, params):
        try:
            X.drop(self.group_by_key, axis=1, inplace=True)
        except:
            pass
        try:
            X.drop('output', axis=1, inplace=True)
        except:
            pass
        Z = 0
        for i,var in enumerate(self.variables):
            Z += params[i] * X[var]
        return Z.rename('response')
        
    def log_likelihood_student(self, X, y, params):
        if len(X)!=len(y):
            print('Training dataset and output should be of same size.')
            return None
        X.reset_index(drop=True,inplace=True)
        y.reset_index(drop=True,inplace=True)
        Z = np.array(self.response_function(X,params))
        if nCr(len(y),sum(y)) <= 100:
            perms = unique_permutations(y)
        else:
            perms = [np.random.permutation(y) for _ in range(100)]
        result = []
        for a in perms:
            result.append(np.exp(Z.dot(a)))
        result = Z.dot(np.array(y)) - log(sum(result))
        return result
            
    def log_likelihood(self, X, y, params):
        X['output'] = y
        result = sum(np.array(X.groupby(self.group_by_key).apply(lambda group : \
            self.log_likelihood_student(group,group['output'],params))))
        return result
        
    def conditional_probability(self, X, y, params):
        if nCr(len(y),sum(y)) <= 100:
            perms = unique_permutations(y)
        else:
            perms = [np.random.permutation(y) for _ in range(100)]
        result = []
        for z in perms:
            result.append(exp(np.array(z).T.dot(np.array(X).dot(params))))
        result = np.sum(np.array(result), axis=0)
        result = exp(np.array(y).T.dot(np.array(X).dot(params))) / result
        return result
    
    def score_student(self, X, y, params):
        if len(X)!=len(y):
            print('Training dataset and output should be of same size.')
            return None
        try:
            X.drop(self.group_by_key, axis=1, inplace=True)
        except:
            pass
        try:
            X.drop('output', axis=1, inplace=True)
        except:
            pass
        X.reset_index(drop=True,inplace=True)
        y.reset_index(drop=True,inplace=True)
        if sum(y)==0 or sum(y)==len(y):
            return np.array([0 for _ in range(len(X.columns))])
        else:
            if nCr(len(y),sum(y)) <= 100:
                perms = unique_permutations(y)
            else:
                perms = [np.random.permutation(y) for _ in range(100)]
            result = []
            for z in perms:
                result.append(np.array(z) * self.conditional_probability(X,z,params))
            result = np.sum(np.array(result), axis=0)
            result = np.array(X).T.dot(np.array(y) - result)
            return result
            
    def hessian_student(self, X, y, params):
        if len(X)!=len(y):
            print('Training dataset and output should be of same size.')
            return None
        try:
            X.drop(self.group_by_key, axis=1, inplace=True)
        except:
            pass
        try:
            X.drop('output', axis=1, inplace=True)
        except:
            pass
        X.reset_index(drop=True,inplace=True)
        y.reset_index(drop=True,inplace=True)
        if sum(y)==0 or sum(y)==len(y):
            return np.array([[0 for _ in range(len(X.columns))] for _ in range(len(X.columns))])
        else:
            if nCr(len(y),sum(y)) <= 100:
                perms = unique_permutations(y)
            else:
                perms = [list(np.random.permutation(y)) for _ in range(100)]
            probas = []
            esp = []
            result = []
            i = 0
            for z in perms:
                probas.append(self.conditional_probability(X,z,params))
                esp.append(np.array(z) * probas[i])
                result.append(np.array(z).dot(np.array(z).T) * probas[i])
                i += 1
            esp = np.sum(np.array(esp), axis=0)
            result = np.sum(np.array(result), axis=0)
            result = np.array(X).T.dot(
                result - esp.T.dot(esp)).dot(np.array(X))
            return result

    def fit(self, X, y, group_by_key, nb_iter=50):
        X['output'] = y
        X['constant'] = 1
        
        self.nb_obs = len(X)
        self.variables = [x for x in X.columns if (x!=group_by_key and x!='output')]
        self.group_by_key = group_by_key
        
        params_init = [0 for _ in range(len(self.variables))]   
        self.params_est = np.zeros((nb_iter,len(params_init)))
        self.params_est[0] = params_init
        self.init_ll = self.log_likelihood(X,y,params_init)
        print('Initial log-likelihood : '+ str(self.init_ll))
        print('Parameters estimation in progress.')
        
        j = 1
        while (j < nb_iter) and (j == 1 or sqrt(sum([(self.params_est[j,k] \
            - self.params_est[j-1,k])**2 for k in range(len(params_init))])) > 0.05):
            
            score = sum(np.array(X.groupby(group_by_key).apply(lambda group : \
                self.score_student(group, group['output'],
                self.params_est[j-1]))))

            hessian = sum(np.array(X.groupby(group_by_key).apply(lambda group : \
                self.hessian_student(group,group['output'],self.params_est[j-1]))))

            try:
                self.params_est[j] = self.params_est[j-1] + inv(hessian).dot(score)                
                print('Iteration '+str(j)+', log_likelihood : '\
                    + str(self.log_likelihood(X,y,self.params_est[j])))
                j += 1
            except:
                print('Improper classification problem')
                return self
        self.params = self.params_est[-1]
        self.final_ll = self.log_likelihood(X,y,self.params)
        if j < nb_iter:
            self.converged = True
        else:
            self.converged = False
        return self
        
    def predict(self, X):
        try :
            self.params
        except:
            print('Fit method should be called before evaluation of the model.')
            print('The following model is a benchmark with all coefficients normalized.')
            self.params = [1 for _ in range(4)]
        Z = self.response_function(X,self.params)
        result = (np.sign(Z)+1)/2
        return result.astype(int).rename('predicted_values')
        
    def predict_proba(self, X):
        try :
            self.params
        except:
            print('Fit method should be called before evaluation of the model.')
            print('The following model is a benchmark with all coefficients normalized.')
            self.params = [1 for _ in range(4)]
        Z = self.response_function(X,self.params)
        return Z.apply(lambda x : norm_cdf(x))
        
    def beta(self):
        try:
            return self.params
        except:
            print('Fit method should be called before evaluation of the model.')
            
    def beta_std(self):
        try:
            return None
        except:
            print('Fit method should be called before evaluation of the model.')
            
    def plot_est(self):
        try:
            self.params
        except:
            print('Fit method should be called before evaluation of the model.')
            return
            
        colors = ['b','g','r','c','m','y','k']
        for k in range(len(self.params)):
            plt.plot(np.arange(1,len(self.params_est)+1),self.params_est[:,k],
                color=colors[k-1],label="Beta_"+str(k))
        plt.xlim((1,len(self.params_est)*1.2))
        plt.xlabel('Iterations')
        plt.ylabel('Estimators')
        plt.title('Trace plot of estimators of beta', size=16)
        plt.legend(loc='best')
        
    def summary(self):
        try:
            self.params
        except:
            print('Fit method should be called before evaluation of the model.')
            return
            
        print('Logit Regression on Panel Data')
        print('============================================================')
        print('%-30s %-30s' \
            % ('Dep. Variable: has_applied','No. Observations: %s' % str(self.nb_obs)))
        print('%-30s %-30s' \
            % ('Model: Panel Logit','Df Model: %s' % str(len(self.params))))
        print('%-30s %-30s' \
            % ('Method: MLE','Pseudo R-squ.: %s' 
            % ("%.5f" % (1-self.final_ll/self.init_ll))))
        print('%-30s %-30s' \
            % ('Converged: %s' % self.converged,'Log-Likelihood: %s' 
            % ("%.1f" % self.final_ll)))
        print('%-30s %-30s' \
            % (' ','LL-Null: %s' % ("%.1f" % self.init_ll)))
        print('%-30s %-30s' \
            % (' ','LLR p-value: %s' \
            % ("%.3f" % (1-st.chi2.cdf(-2*log(1-self.final_ll/self.init_ll),
            len(self.params))))))
        print('============================================================\n')
#        length = max([len(x) for x in self.variables if (x != self.group_by_key and x != 'output')])
#        print('%-*s %-8s %-8s %-8s %-8s %-18s' \
#              % ((length+4,' '), 'coef', 'std err', 't', 'P>|t|', '[95.0% Conf. Int.]'))
#        for i,var in enumerate([x for x in self.variables if (x != self.group_by_key and x != 'output')]):
#            print('%-*s %-8s %-8s %-8s %-8s %-8s %-8s' \
#                % (length+4,var, self.params[i], 0, 0, 0, 0, 0))
        